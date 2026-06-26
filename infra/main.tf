provider "aws" {
  region = "ap-northeast-1"
}

variable "ecr_image_uri" {
  description = "Enter your ECR Image URI (must include the :latest tag)"
  type        = string
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "hydra-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_cluster" "hydra_cluster" {
  name = "hydra-cluster"
}

data "aws_vpc" "default" { default = true }

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "hydra_sg" {
  name   = "hydra-ecs-sg"
  vpc_id = data.aws_vpc.default.id

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  ingress {
    from_port   = 8001
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ElastiCache needs a subnet group
resource "aws_elasticache_subnet_group" "hydra_redis" {
  name       = "hydra-redis-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
}

# Security group for Redis (only allow ECS to connect)
resource "aws_security_group" "redis_sg" {
  name   = "hydra-redis-sg"
  vpc_id = data.aws_vpc.default.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.hydra_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "hydra_redis" {
  cluster_id           = "hydra-redis"
  engine               = "redis"
  node_type            = "cache.t4g.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.hydra_redis.name
  security_group_ids   = [aws_security_group.redis_sg.id]
}

# Output Redis endpoint
output "redis_endpoint" {
  value = aws_elasticache_cluster.hydra_redis.cache_nodes[0].address
}

resource "aws_service_discovery_private_dns_namespace" "hydra" {
  name        = "hydra.local"
  description = "Hydra internal service discovery"
  vpc         = data.aws_vpc.default.id
}

resource "aws_service_discovery_service" "mock" {
  name = "mock"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.hydra.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_cloudwatch_log_group" "hydra_logs" {
  name              = "/ecs/hydra-gateway"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "mock_logs" {
  name              = "/ecs/hydra-mock"
  retention_in_days = 7
}

resource "aws_ecs_task_definition" "hydra_task" {
  family                   = "hydra-gateway"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([{
    name      = "hydra-gateway"
    image     = var.ecr_image_uri
    essential = true

    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]

    environment = [
      { name = "MANAGER_TYPE",        value = "redis" },
      { name = "PORT",                value = "8080" },
      { name = "REDIS_HOST",          value = aws_elasticache_cluster.hydra_redis.cache_nodes[0].address },
      { name = "REDIS_PORT",          value = "6379" },
      { name = "GEMINI_API_BASE_URL", value = "http://mock.hydra.local:8001" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/ecs/hydra-gateway"
        awslogs-region        = "ap-northeast-1"
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "mock_task" {
  family                   = "hydra-mock"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([{
    name      = "hydra-mock"
    image     = "308621094790.dkr.ecr.ap-northeast-1.amazonaws.com/hydra-mock-repo:latest"
    essential = true

    portMappings = [{
      containerPort = 8001
      protocol      = "tcp"
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/ecs/hydra-mock"
        awslogs-region        = "ap-northeast-1"
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "hydra_service" {
  name            = "hydra-gateway-service"
  cluster         = aws_ecs_cluster.hydra_cluster.id
  task_definition = aws_ecs_task_definition.hydra_task.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.hydra_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.hydra_tg.arn
    container_name   = "hydra-gateway"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.hydra_listener]
}

resource "aws_ecs_service" "mock_service" {
  name            = "hydra-mock-service"
  cluster         = aws_ecs_cluster.hydra_cluster.id
  task_definition = aws_ecs_task_definition.mock_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.hydra_sg.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.mock.arn
  }
}

# ALB
resource "aws_lb" "hydra_alb" {
  name               = "hydra-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = data.aws_subnets.default.ids
}

# ALB Security Group
resource "aws_security_group" "alb_sg" {
  name   = "hydra-alb-sg"
  vpc_id = data.aws_vpc.default.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Target Group
resource "aws_lb_target_group" "hydra_tg" {
  name        = "hydra-gateway-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

# Listener
resource "aws_lb_listener" "hydra_listener" {
  load_balancer_arn = aws_lb.hydra_alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.hydra_tg.arn
  }
}

# Output ALB DNS
output "alb_dns" {
  value = "http://${aws_lb.hydra_alb.dns_name}"
}
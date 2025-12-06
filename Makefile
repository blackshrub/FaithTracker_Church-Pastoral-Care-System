# FaithTracker Docker Management
# ================================
# Standardized commands for Docker operations
#
# Quick Reference:
#   make up        - Start all services (production)
#   make down      - Stop all services
#   make restart   - Restart all services
#   make logs      - View all logs (follow)
#   make build     - Build images (uses cache)
#   make rebuild   - Build images without cache (fresh build)
#   make status    - Show service status
#
# Individual Services:
#   make restart-backend   - Restart only backend
#   make rebuild-frontend  - Rebuild frontend without cache
#   make logs-backend      - View backend logs only
#
# Database:
#   make backup    - Backup MongoDB
#   make shell-db  - Open MongoDB shell
#
# Troubleshooting:
#   make health    - Check all service health
#   make clean     - Remove unused Docker resources

.PHONY: help up down restart logs build rebuild status health clean \
        restart-backend restart-frontend rebuild-backend rebuild-frontend \
        logs-backend logs-frontend logs-mongo logs-traefik \
        backup shell-db shell-backend ps

# Default target - show help
.DEFAULT_GOAL := help

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m
BOLD := \033[1m

#===============================================================================
# HELP
#===============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)$(BOLD)FaithTracker Docker Commands$(NC)"
	@echo "$(CYAN)==============================$(NC)"
	@echo ""
	@echo "$(BOLD)Quick Start:$(NC)"
	@echo "  $(GREEN)make up$(NC)              Start all services"
	@echo "  $(GREEN)make down$(NC)            Stop all services"
	@echo "  $(GREEN)make restart$(NC)         Restart all services"
	@echo "  $(GREEN)make logs$(NC)            View logs (follow mode)"
	@echo "  $(GREEN)make status$(NC)          Show service status"
	@echo ""
	@echo "$(BOLD)Building:$(NC)"
	@echo "  $(GREEN)make build$(NC)           Build with cache (fast)"
	@echo "  $(GREEN)make rebuild$(NC)         Build without cache (fresh)"
	@echo "  $(GREEN)make rebuild-backend$(NC) Rebuild backend only (no cache)"
	@echo "  $(GREEN)make rebuild-frontend$(NC) Rebuild frontend only (no cache)"
	@echo ""
	@echo "$(BOLD)Individual Services:$(NC)"
	@echo "  $(GREEN)make restart-backend$(NC)  Restart backend only"
	@echo "  $(GREEN)make restart-frontend$(NC) Restart frontend only"
	@echo "  $(GREEN)make logs-backend$(NC)     View backend logs"
	@echo "  $(GREEN)make logs-frontend$(NC)    View frontend logs"
	@echo "  $(GREEN)make logs-mongo$(NC)       View MongoDB logs"
	@echo "  $(GREEN)make logs-traefik$(NC)     View Traefik logs"
	@echo ""
	@echo "$(BOLD)Database:$(NC)"
	@echo "  $(GREEN)make backup$(NC)          Backup MongoDB to ./backups/"
	@echo "  $(GREEN)make shell-db$(NC)        Open MongoDB shell"
	@echo ""
	@echo "$(BOLD)Troubleshooting:$(NC)"
	@echo "  $(GREEN)make health$(NC)          Check service health"
	@echo "  $(GREEN)make clean$(NC)           Remove unused Docker resources"
	@echo "  $(GREEN)make prune$(NC)           Deep clean (removes all unused)"
	@echo ""
	@echo "$(BOLD)When to use --no-cache (rebuild):$(NC)"
	@echo "  $(YELLOW)•$(NC) After updating requirements.txt or package.json"
	@echo "  $(YELLOW)•$(NC) After updating Dockerfile"
	@echo "  $(YELLOW)•$(NC) When build behaves unexpectedly"
	@echo "  $(YELLOW)•$(NC) First deploy on new server"
	@echo ""

#===============================================================================
# MAIN COMMANDS
#===============================================================================

up: ## Start all services
	@echo "$(GREEN)Starting all services...$(NC)"
	docker compose up -d
	@echo "$(GREEN)Services started. Use 'make logs' to view output.$(NC)"

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker compose down
	@echo "$(GREEN)All services stopped.$(NC)"

restart: ## Restart all services
	@echo "$(YELLOW)Restarting all services...$(NC)"
	docker compose restart
	@echo "$(GREEN)All services restarted.$(NC)"

logs: ## View all logs (follow mode)
	docker compose logs -f --tail=100

status: ps ## Show service status (alias: ps)
ps: ## Show running containers
	@echo "$(CYAN)$(BOLD)Service Status$(NC)"
	@echo "$(CYAN)===============$(NC)"
	@docker compose ps
	@echo ""

#===============================================================================
# BUILD COMMANDS
#===============================================================================

build: ## Build images with cache (fast, use for code changes)
	@echo "$(GREEN)Building with cache...$(NC)"
	@echo "$(YELLOW)Tip: Use 'make rebuild' if dependencies changed$(NC)"
	docker compose build

rebuild: ## Build images without cache (fresh, use when deps change)
	@echo "$(GREEN)Building without cache (fresh build)...$(NC)"
	@echo "$(YELLOW)This will take longer but ensures clean build$(NC)"
	docker compose build --no-cache

rebuild-backend: ## Rebuild backend without cache
	@echo "$(GREEN)Rebuilding backend (no cache)...$(NC)"
	docker compose build --no-cache backend
	@echo "$(YELLOW)Run 'make restart-backend' to apply changes$(NC)"

rebuild-frontend: ## Rebuild frontend without cache
	@echo "$(GREEN)Rebuilding frontend (no cache)...$(NC)"
	docker compose build --no-cache frontend
	@echo "$(YELLOW)Run 'make restart-frontend' to apply changes$(NC)"

#===============================================================================
# INDIVIDUAL SERVICE COMMANDS
#===============================================================================

restart-backend: ## Restart backend only
	@echo "$(YELLOW)Restarting backend...$(NC)"
	docker compose restart backend
	@echo "$(GREEN)Backend restarted.$(NC)"

restart-frontend: ## Restart frontend only
	@echo "$(YELLOW)Restarting frontend...$(NC)"
	docker compose restart frontend
	@echo "$(GREEN)Frontend restarted.$(NC)"

restart-traefik: ## Restart Traefik (reverse proxy)
	@echo "$(YELLOW)Restarting Traefik...$(NC)"
	docker compose restart traefik
	@echo "$(GREEN)Traefik restarted.$(NC)"

logs-backend: ## View backend logs
	docker compose logs -f --tail=100 backend

logs-frontend: ## View frontend logs
	docker compose logs -f --tail=100 frontend

logs-mongo: ## View MongoDB logs
	docker compose logs -f --tail=100 mongo

logs-traefik: ## View Traefik logs
	docker compose logs -f --tail=100 traefik

#===============================================================================
# DATABASE COMMANDS
#===============================================================================

backup: ## Backup MongoDB to ./backups/
	@echo "$(GREEN)Creating MongoDB backup...$(NC)"
	@mkdir -p backups
	@docker exec faithtracker-mongo mongodump \
		--uri="mongodb://$(shell grep MONGO_ROOT_USERNAME .env | cut -d= -f2):$(shell grep MONGO_ROOT_PASSWORD .env | cut -d= -f2)@localhost:27017/faithtracker?authSource=admin" \
		--archive=/tmp/backup.archive \
		--gzip
	@docker cp faithtracker-mongo:/tmp/backup.archive ./backups/faithtracker_$(shell date +%Y%m%d_%H%M%S).archive
	@echo "$(GREEN)Backup saved to ./backups/$(NC)"

shell-db: ## Open MongoDB shell
	@echo "$(CYAN)Opening MongoDB shell...$(NC)"
	@echo "$(YELLOW)Type 'exit' to quit$(NC)"
	@docker exec -it faithtracker-mongo mongosh \
		"mongodb://$(shell grep MONGO_ROOT_USERNAME .env | cut -d= -f2):$(shell grep MONGO_ROOT_PASSWORD .env | cut -d= -f2)@localhost:27017/faithtracker?authSource=admin"

shell-backend: ## Open backend container shell
	@echo "$(CYAN)Opening backend shell...$(NC)"
	docker exec -it faithtracker-backend /bin/sh

#===============================================================================
# HEALTH & TROUBLESHOOTING
#===============================================================================

health: ## Check service health
	@echo "$(CYAN)$(BOLD)Health Check$(NC)"
	@echo "$(CYAN)=============$(NC)"
	@echo ""
	@echo "$(BOLD)Container Status:$(NC)"
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "$(BOLD)API Health:$(NC)"
	@curl -sf https://api.pastoral.gkbj.org/health && echo " $(GREEN)✓ API is healthy$(NC)" || echo " $(RED)✗ API not responding$(NC)"
	@echo ""
	@echo "$(BOLD)Frontend:$(NC)"
	@curl -sf -o /dev/null https://pastoral.gkbj.org && echo " $(GREEN)✓ Frontend is accessible$(NC)" || echo " $(RED)✗ Frontend not responding$(NC)"
	@echo ""

clean: ## Remove unused Docker resources (safe)
	@echo "$(YELLOW)Cleaning unused Docker resources...$(NC)"
	docker system prune -f
	@echo "$(GREEN)Cleanup complete.$(NC)"

prune: ## Deep clean - remove ALL unused resources (careful!)
	@echo "$(RED)$(BOLD)WARNING: This will remove ALL unused images, containers, networks$(NC)"
	@read -p "Are you sure? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	docker system prune -a -f --volumes
	@echo "$(GREEN)Deep cleanup complete.$(NC)"

#===============================================================================
# DEPLOYMENT (common workflows)
#===============================================================================

deploy: ## Full deployment: rebuild and restart all
	@echo "$(GREEN)$(BOLD)Starting full deployment...$(NC)"
	@echo ""
	$(MAKE) backup
	@echo ""
	$(MAKE) rebuild
	@echo ""
	docker compose up -d
	@echo ""
	@sleep 5
	$(MAKE) health
	@echo ""
	@echo "$(GREEN)$(BOLD)Deployment complete!$(NC)"

deploy-backend: ## Deploy backend only (rebuild + restart)
	@echo "$(GREEN)Deploying backend...$(NC)"
	$(MAKE) rebuild-backend
	docker compose up -d backend
	@echo "$(GREEN)Backend deployed.$(NC)"

deploy-frontend: ## Deploy frontend only (rebuild + restart)
	@echo "$(GREEN)Deploying frontend...$(NC)"
	$(MAKE) rebuild-frontend
	docker compose up -d frontend
	@echo "$(GREEN)Frontend deployed.$(NC)"

quick-deploy: ## Quick deploy: build with cache and restart
	@echo "$(GREEN)$(BOLD)Quick deployment (with cache)...$(NC)"
	$(MAKE) build
	docker compose up -d
	@echo "$(GREEN)Quick deploy complete.$(NC)"

#===============================================================================
# CACHE MANAGEMENT
#===============================================================================

clear-cache: ## Clear dashboard cache in MongoDB
	@echo "$(YELLOW)Clearing dashboard cache...$(NC)"
	@docker exec faithtracker-mongo mongosh \
		"mongodb://$(shell grep MONGO_ROOT_USERNAME .env | cut -d= -f2):$(shell grep MONGO_ROOT_PASSWORD .env | cut -d= -f2)@localhost:27017/faithtracker?authSource=admin" \
		--quiet --eval "db.dashboard_cache.deleteMany({})"
	@echo "$(GREEN)Dashboard cache cleared.$(NC)"

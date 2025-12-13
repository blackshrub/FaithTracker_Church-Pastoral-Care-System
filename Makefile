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
# Angie (Host-level Web Server):
#   make angie-install   - Install Angie and dependencies
#   make angie-status    - Check Angie status
#   make angie-reload    - Reload Angie configuration
#   make angie-test      - Test Angie configuration
#   make angie-logs      - View Angie logs
#   make ssl-setup       - Setup SSL certificates
#   make ssl-renew       - Force certificate renewal
#
# Individual Services:
#   make restart-backend   - Restart only backend
#   make rebuild-frontend  - Rebuild frontend without cache
#   make logs-backend      - View backend logs
#
# Database & Backups:
#   make backup       - Backup MongoDB only
#   make backup-full  - Backup MongoDB + uploads (recommended)
#   make backup-list  - List available backups
#   make shell-db     - Open MongoDB shell
#
# Troubleshooting:
#   make health    - Check all service health
#   make clean     - Remove unused Docker resources

.PHONY: help up down restart logs build rebuild status health clean \
        restart-backend restart-frontend rebuild-backend rebuild-frontend \
        logs-backend logs-frontend logs-mongo \
        backup shell-db shell-backend ps \
        angie-install angie-status angie-reload angie-test angie-logs \
        ssl-setup ssl-renew ssl-status

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
	@echo "$(BOLD)Angie Web Server (Host-level):$(NC)"
	@echo "  $(GREEN)make angie-install$(NC)   Install Angie and Certbot"
	@echo "  $(GREEN)make angie-status$(NC)    Check Angie status"
	@echo "  $(GREEN)make angie-reload$(NC)    Reload Angie configuration"
	@echo "  $(GREEN)make angie-test$(NC)      Test configuration syntax"
	@echo "  $(GREEN)make angie-logs$(NC)      View Angie logs"
	@echo ""
	@echo "$(BOLD)SSL Certificates:$(NC)"
	@echo "  $(GREEN)make ssl-setup$(NC)       Setup SSL certificates"
	@echo "  $(GREEN)make ssl-renew$(NC)       Force certificate renewal"
	@echo "  $(GREEN)make ssl-status$(NC)      Check certificate status"
	@echo ""
	@echo "$(BOLD)Individual Services:$(NC)"
	@echo "  $(GREEN)make restart-backend$(NC)  Restart backend only"
	@echo "  $(GREEN)make restart-frontend$(NC) Restart frontend only"
	@echo "  $(GREEN)make logs-backend$(NC)     View backend logs"
	@echo "  $(GREEN)make logs-frontend$(NC)    View frontend logs"
	@echo "  $(GREEN)make logs-mongo$(NC)       View MongoDB logs"
	@echo ""
	@echo "$(BOLD)Database & Backups:$(NC)"
	@echo "  $(GREEN)make backup$(NC)          Backup MongoDB only"
	@echo "  $(GREEN)make backup-full$(NC)     Backup MongoDB + uploads (recommended)"
	@echo "  $(GREEN)make backup-list$(NC)     List available backups"
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
	@echo "$(CYAN)$(BOLD)Angie Status$(NC)"
	@echo "$(CYAN)=============$(NC)"
	@systemctl is-active angie 2>/dev/null && echo "  Angie: $(GREEN)running$(NC)" || echo "  Angie: $(RED)stopped$(NC)"
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
# ANGIE WEB SERVER COMMANDS (Host-level)
#===============================================================================

angie-install: ## Install Angie web server and Certbot
	@echo "$(GREEN)Installing Angie...$(NC)"
	@echo "$(YELLOW)This requires root privileges$(NC)"
	sudo ./angie/install.sh

angie-status: ## Check Angie status
	@echo "$(CYAN)$(BOLD)Angie Status$(NC)"
	@echo "$(CYAN)=============$(NC)"
	@systemctl status angie --no-pager -l || true

angie-reload: ## Reload Angie configuration
	@echo "$(YELLOW)Reloading Angie configuration...$(NC)"
	sudo systemctl reload angie
	@echo "$(GREEN)Angie reloaded.$(NC)"

angie-test: ## Test Angie configuration syntax
	@echo "$(CYAN)Testing Angie configuration...$(NC)"
	sudo angie -t

angie-logs: ## View Angie logs
	sudo journalctl -u angie -f --no-pager -n 100

angie-access-logs: ## View Angie access logs
	sudo tail -f /var/log/angie/access.log

#===============================================================================
# SSL CERTIFICATE COMMANDS
#===============================================================================

ssl-setup: ## Setup SSL certificates with Certbot
	@echo "$(GREEN)Setting up SSL certificates...$(NC)"
	@echo "$(YELLOW)This requires root privileges$(NC)"
	sudo ./angie/setup-ssl.sh

ssl-renew: ## Force certificate renewal
	@echo "$(YELLOW)Forcing certificate renewal...$(NC)"
	sudo certbot renew --force-renewal
	sudo systemctl reload angie
	@echo "$(GREEN)Certificates renewed and Angie reloaded.$(NC)"

ssl-status: ## Check SSL certificate status
	@echo "$(CYAN)$(BOLD)SSL Certificate Status$(NC)"
	@echo "$(CYAN)======================$(NC)"
	@sudo certbot certificates 2>/dev/null || echo "Certbot not installed or no certificates"

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

logs-backend: ## View backend logs
	docker compose logs -f --tail=100 backend

logs-frontend: ## View frontend logs
	docker compose logs -f --tail=100 frontend

logs-mongo: ## View MongoDB logs
	docker compose logs -f --tail=100 mongo

#===============================================================================
# DATABASE COMMANDS
#===============================================================================

backup: ## Backup MongoDB to ./backups/
	@echo "$(GREEN)Creating MongoDB backup...$(NC)"
	@./scripts/backup-db.sh

backup-full: ## Backup MongoDB + uploads to ./backups/
	@echo "$(GREEN)Creating full backup (database + uploads)...$(NC)"
	@./scripts/backup-db.sh --full

backup-list: ## List available backups
	@./scripts/backup-db.sh --list

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
	@echo "$(BOLD)Angie (Host-level):$(NC)"
	@systemctl is-active angie 2>/dev/null && echo "  $(GREEN)✓ Angie is running$(NC)" || echo "  $(RED)✗ Angie not running$(NC)"
	@echo ""
	@echo "$(BOLD)Docker Containers:$(NC)"
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "$(BOLD)Backend Health:$(NC)"
	@curl -sf http://127.0.0.1:8001/health && echo " $(GREEN)✓ Backend is healthy$(NC)" || echo " $(RED)✗ Backend not responding$(NC)"
	@echo ""
	@echo "$(BOLD)Frontend Health:$(NC)"
	@curl -sf http://127.0.0.1:8080/health && echo " $(GREEN)✓ Frontend is healthy$(NC)" || echo " $(RED)✗ Frontend not responding$(NC)"
	@echo ""
	@if [ -f .env ]; then \
		DOMAIN=$$(grep ^DOMAIN= .env | cut -d= -f2 | tr -d '"'); \
		if [ -n "$$DOMAIN" ]; then \
			echo "$(BOLD)External Access:$(NC)"; \
			curl -sf -o /dev/null "https://$$DOMAIN" && echo "  $(GREEN)✓ https://$$DOMAIN accessible$(NC)" || echo "  $(YELLOW)⚠ https://$$DOMAIN not accessible$(NC)"; \
			curl -sf -o /dev/null "https://api.$$DOMAIN/health" && echo "  $(GREEN)✓ https://api.$$DOMAIN accessible$(NC)" || echo "  $(YELLOW)⚠ https://api.$$DOMAIN not accessible$(NC)"; \
		fi; \
	fi
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

#===============================================================================
# FIRST-TIME SETUP
#===============================================================================

setup: ## First-time setup: install Angie, get SSL, start services
	@echo "$(GREEN)$(BOLD)FaithTracker First-Time Setup$(NC)"
	@echo ""
	@echo "Step 1: Installing Angie web server..."
	$(MAKE) angie-install
	@echo ""
	@echo "Step 2: Setting up SSL certificates..."
	$(MAKE) ssl-setup
	@echo ""
	@echo "Step 3: Building Docker images..."
	$(MAKE) build
	@echo ""
	@echo "Step 4: Starting services..."
	$(MAKE) up
	@echo ""
	@echo "Step 5: Checking health..."
	@sleep 10
	$(MAKE) health
	@echo ""
	@echo "$(GREEN)$(BOLD)Setup complete!$(NC)"

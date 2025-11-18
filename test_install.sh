#!/bin/bash

###############################################################################
# Installation Script Test Suite
# Tests individual components without requiring root access
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

print_fail() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

# Test 1: Check if install script exists
test_script_exists() {
    print_test "Checking if installation scripts exist"
    
    if [ -f "/app/install_improved.sh" ]; then
        print_pass "install_improved.sh exists"
    else
        print_fail "install_improved.sh not found"
    fi
    
    if [ -x "/app/install_improved.sh" ]; then
        print_pass "install_improved.sh is executable"
    else
        print_fail "install_improved.sh is not executable"
    fi
}

# Test 2: Check bash syntax
test_syntax() {
    print_test "Checking bash syntax"
    
    if bash -n /app/install_improved.sh 2>/dev/null; then
        print_pass "Bash syntax is valid"
    else
        print_fail "Syntax errors detected"
        bash -n /app/install_improved.sh
    fi
}

# Test 3: Test helper functions
test_helper_functions() {
    print_test "Testing helper functions"
    
    # Source just the helper functions
    eval "$(sed -n '/^# HELPER FUNCTIONS/,/^# INSTALLATION FUNCTIONS/p' /app/install_improved.sh | head -n -1)"
    
    # Test email validation
    if validate_email "test@example.com"; then
        print_pass "Email validation works correctly"
    else
        print_fail "Email validation failed for valid email"
    fi
    
    if ! validate_email "invalid-email"; then
        print_pass "Email validation rejects invalid emails"
    else
        print_fail "Email validation accepted invalid email"
    fi
    
    # Test domain validation
    if validate_domain "faithtracker.com"; then
        print_pass "Domain validation works correctly"
    else
        print_fail "Domain validation failed for valid domain"
    fi
}

# Test 4: Check required files
test_required_files() {
    print_test "Checking required application files"
    
    REQUIRED_FILES=(
        "/app/backend/server.py"
        "/app/backend/requirements.txt"
        "/app/frontend/package.json"
        "/app/frontend/src/App.js"
        "/app/.env.example"
        "/app/README.md"
        "/app/docs/FEATURES.md"
        "/app/docs/API.md"
        "/app/docs/DEPLOYMENT_DEBIAN.md"
    )
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [ -f "$file" ]; then
            print_pass "Found: $file"
        else
            print_fail "Missing: $file"
        fi
    done
}

# Test 5: Check documentation completeness
test_documentation() {
    print_test "Checking documentation completeness"
    
    # Check README has key sections
    if grep -q "Quick Start" /app/README.md && \
       grep -q "Features" /app/README.md && \
       grep -q "Installation" /app/README.md; then
        print_pass "README.md contains key sections"
    else
        print_fail "README.md missing important sections"
    fi
    
    # Check API docs have endpoints
    if grep -q "POST /api" /app/docs/API.md && \
       grep -q "GET /api" /app/docs/API.md; then
        print_pass "API documentation includes endpoints"
    else
        print_fail "API documentation incomplete"
    fi
    
    # Check deployment guide has systemd
    if grep -q "systemd" /app/docs/DEPLOYMENT_DEBIAN.md && \
       grep -q "nginx" /app/docs/DEPLOYMENT_DEBIAN.md; then
        print_pass "Deployment guide includes systemd and nginx"
    else
        print_fail "Deployment guide incomplete"
    fi
}

# Test 6: Verify environment example
test_env_example() {
    print_test "Checking .env.example"
    
    REQUIRED_VARS=(
        "MONGO_URL"
        "JWT_SECRET_KEY"
        "REACT_APP_BACKEND_URL"
    )
    
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "$var" /app/.env.example; then
            print_pass "Found required variable: $var"
        else
            print_fail "Missing variable in .env.example: $var"
        fi
    done
}

# Test 7: Test Python requirements
test_python_requirements() {
    print_test "Checking Python requirements.txt"
    
    if [ -f "/app/backend/requirements.txt" ]; then
        REQUIRED_PACKAGES=("fastapi" "uvicorn" "motor" "pydantic")
        
        for pkg in "${REQUIRED_PACKAGES[@]}"; do
            if grep -qi "$pkg" /app/backend/requirements.txt; then
                print_pass "Found Python package: $pkg"
            else
                print_fail "Missing Python package: $pkg"
            fi
        done
    else
        print_fail "requirements.txt not found"
    fi
}

# Test 8: Test frontend package.json
test_frontend_packages() {
    print_test "Checking frontend package.json"
    
    if [ -f "/app/frontend/package.json" ]; then
        REQUIRED_PACKAGES=("react" "axios" "@tanstack/react-query")
        
        for pkg in "${REQUIRED_PACKAGES[@]}"; do
            if grep -q "\"$pkg\"" /app/frontend/package.json; then
                print_pass "Found Node package: $pkg"
            else
                print_fail "Missing Node package: $pkg"
            fi
        done
    else
        print_fail "package.json not found"
    fi
}

# Test 9: Check install script user prompts
test_user_prompts() {
    print_test "Checking user prompts in install script"
    
    REQUIRED_PROMPTS=("domain" "email" "password" "MongoDB")
    
    for prompt in "${REQUIRED_PROMPTS[@]}"; do
        if grep -qi "$prompt" /app/install_improved.sh; then
            print_pass "Install script prompts for: $prompt"
        else
            print_fail "Install script missing prompt for: $prompt"
        fi
    done
}

# Test 10: Verify gitignore
test_gitignore() {
    print_test "Checking .gitignore"
    
    SHOULD_IGNORE=(".env" "node_modules" "__pycache__" "venv")
    
    for pattern in "${SHOULD_IGNORE[@]}"; do
        if grep -q "$pattern" /app/.gitignore; then
            print_pass ".gitignore includes: $pattern"
        else
            print_fail ".gitignore missing: $pattern"
        fi
    done
}

# Run all tests
echo ""
echo "=========================================="
echo "  FaithTracker Installation Test Suite"
echo "=========================================="
echo ""

test_script_exists
test_syntax
test_helper_functions
test_required_files
test_documentation
test_env_example
test_python_requirements
test_frontend_packages
test_user_prompts
test_gitignore

echo ""
echo "=========================================="
echo "           Test Summary"
echo "=========================================="
echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo "The installation script is ready for deployment."
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo "Please review the failures above."
    exit 1
fi

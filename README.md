# 🎉 GKBJ Pastoral Care System

## Enterprise-Grade Church Member Care Management with AI Intelligence

[![Production Ready](https://img.shields.io/badge/Production-Ready-green.svg)](https://member-care.preview.emergentagent.com)
[![Mobile API Ready](https://img.shields.io/badge/Mobile%20API-Ready-blue.svg)](#mobile-api-integration)
[![PWA Compatible](https://img.shields.io/badge/PWA-Compatible-orange.svg)](#pwa-features)

Enterprise pastoral care system for GKBJ ensuring no member is left behind through systematic coordination, AI intelligence, and automated staff reminders.

## 🎯 **Current Status**

**Production-ready system managing 805+ church members with:**
- **AI-Powered Pastoral Recommendations** with priority scoring
- **Automated Daily WhatsApp Digest** to pastoral staff (verified working)
- **Advanced Financial Aid Scheduling** (weekly/monthly/annual)
- **Dual Timeline Systems** (6-stage grief + 3-stage accident follow-up)
- **Complete API Integration** ready for mobile app development
- **Enterprise Security** with comprehensive validation
- **Real-time Data** prioritized over caching for accuracy

## ✨ **Core Features**

### 🎯 **Member Management (805 Members)**
- **Complete demographics**: Name, phone, age, gender, membership, marital, category, blood type
- **Profile photos**: 657 photos with lazy loading and multi-size optimization
- **Family groups**: 278 household organizations
- **Engagement tracking**: Auto-calculated status (Active/At-Risk/Inactive)
- **Professional search**: Single character minimum with pagination (25/page)
- **Bulk operations**: Multi-select, edit, delete with enterprise validation

### 🤖 **AI Intelligence**
- **Smart recommendations**: Priority-based follow-up suggestions
- **Pattern recognition**: At-risk identification, senior care needs, visitor follow-up
- **Real-time refresh**: Suggestions update after member contact
- **Demographic analysis**: Population trends for strategic planning
- **Urgency scoring**: High/Medium/Low priority with actionable advice

### 💰 **Financial Aid Management**
- **Recurring scheduling**: One-time, Weekly, Monthly, Annual payments
- **Perfect date logic**: Calculates next occurrence from current date
- **Schedule advancement**: Mark distributed → automatically advances to next payment
- **Overdue tracking**: Missed payments accumulate until individually marked
- **Complete transparency**: Recipient lists with profile integration
- **Aid analytics**: Type effectiveness and distribution insights

### 📱 **Mobile App Integration Ready**
- **Complete API coverage**: All data accessible via REST endpoints
- **Configuration endpoints**: Dropdown values, settings, thresholds via API
- **Real-time updates**: No localStorage dependencies
- **Authentication**: JWT tokens for secure mobile access
- **Photo serving**: Optimized image endpoints for mobile apps

### 📊 **Advanced Analytics**
- **Demographics**: Age, gender, membership distribution with custom date ranges
- **Engagement trends**: Member contact patterns and monthly activity
- **Financial intelligence**: Aid effectiveness and spending patterns
- **Care insights**: Event distribution (birthdays excluded for relevance)
- **Predictive analytics**: Priority member identification and recommendations

### 🔒 **Enterprise Security**
- **Data validation**: CSV preview, API testing, confirmation dialogs
- **Role-based access**: Full Admin, Campus Admin, Pastor with appropriate permissions
- **Multi-campus support**: Data isolation and campus-specific access
- **Audit trails**: Complete logging of all pastoral activities

## 🏗️ **Architecture**

### **Backend (FastAPI + MongoDB)**
- **70+ REST endpoints** with comprehensive CRUD operations
- **Database indexing** for optimized query performance
- **JWT authentication** with role-based access control
- **Automated scheduling** (APScheduler) for daily digest
- **Configuration API** for mobile app integration
- **Photo optimization** with multi-size serving

### **Frontend (React PWA)**
- **Real-time updates** prioritized over caching
- **Professional pagination** (25 items/page) for large datasets
- **Lazy image loading** for optimal performance
- **Mobile-responsive** with horizontal scrolling tabs
- **PWA capability** with home screen installation

## 📱 **Mobile App Integration**

### **Complete API Coverage**
All frontend functionality accessible via REST API:

```http
# Configuration for mobile dropdowns
GET /api/config/all
→ Returns all dropdown values, settings, thresholds

# Member management
GET /api/members?page=1&limit=25&search=john
POST /api/members
PUT /api/members/{id}
DELETE /api/members/{id}

# AI recommendations  
GET /api/suggestions/follow-up
→ Smart pastoral recommendations with priority

# Daily automation
GET /api/dashboard/stats
GET /api/dashboard/upcoming?days=7
GET /api/members/at-risk

# Financial aid scheduling
POST /api/financial-aid-schedules
GET /api/financial-aid-schedules/due-today
POST /api/financial-aid-schedules/{id}/mark-distributed

# Timeline systems
GET /api/grief-support/member/{id}
GET /api/accident-followup/member/{id}
POST /api/grief-support/{id}/complete
```

### **Mobile Development Ready**
- **No localStorage dependencies**: All data via API
- **Configuration endpoints**: Dynamic dropdown population
- **Real-time data**: Fresh information guaranteed
- **Photo optimization**: Multi-size images for different screen densities
- **Authentication**: JWT with role-based permissions

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.11+
- Node.js 18+
- MongoDB 5.0+
- WhatsApp Gateway (configured at dermapack.net:3001)

### **Installation**

```bash
# Backend setup
cd backend
pip install -r requirements.txt
python create_indexes.py  # Performance optimization
python import_data.py     # Load 805 members + photos
python server.py          # Start API server

# Frontend setup
cd frontend
yarn install
yarn start               # Start web interface

# Access
URL: http://localhost:3000
Login: admin@gkbj.church / admin123
```

## 📊 **Production Data**

### **Current Dataset**
- **805 Members** with complete demographic profiles
- **657 Profile Photos** optimized for web and mobile
- **947 Care Events** across all types with automation
- **278 Family Groups** for household organization
- **Active Schedules** for recurring financial aid
- **Timeline Systems** for grief and accident follow-up

### **Verified Working**
- **Daily WhatsApp digest** sending to 6281290080025
- **AI recommendations** with real-time refresh
- **Financial aid advancement** with perfect date calculations
- **Birthday audit trail** with timeline integration
- **Member engagement tracking** with accurate status updates

## 🎯 **Daily Operations**

### **Staff Workflow**
1. **8 AM**: Receive WhatsApp digest with member tasks and wa.me links
2. **Homepage**: View AI suggestions + 6-tab task organization
3. **Task completion**: Mark birthdays/grief/financial aid as complete
4. **Member contact**: Click wa.me links for instant WhatsApp
5. **Financial aid**: Schedule recurring payments, mark distributed
6. **Timeline tracking**: Monitor grief and accident follow-up progress

### **Task Management Tabs**
- **Today**: Birthdays + grief stages due today
- **Follow-up**: Accident recovery + overdue grief support
- **Financial Aid**: Due payments with advancement capability
- **Disconnected**: 90+ days no contact requiring reconnection
- **At Risk**: 60-89 days no contact needing attention
- **Upcoming**: Next 7 days birthdays for planning

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Backend
MONGO_URL="mongodb://localhost:27017"
DB_NAME="pastoral_care_db"
JWT_SECRET_KEY="your-secure-secret"
WHATSAPP_GATEWAY_URL="http://dermapack.net:3001"
CHURCH_NAME="GKBJ"

# Frontend  
REACT_APP_BACKEND_URL="http://localhost:8001"
```

### **Configurable Settings (via API)**
- **Engagement thresholds**: At-risk (60 days), Inactive (90 days)
- **Grief stages**: 6 configurable timelines (default: 7, 14, 30, 90, 180, 365 days)
- **Accident follow-up**: 3 configurable stages (default: 3, 7, 14 days)

## 📱 **Mobile Development**

### **API-First Design**
All configurations and data accessible via REST API for mobile app development:

```http
# Get all configuration data
GET /api/config/all
{
  "aid_types": [{value: "education", label: "Education Support"}],
  "event_types": [{value: "birthday", label: "Birthday"}],
  "settings": {
    "engagement": {atRiskDays: 60, inactiveDays: 90},
    "grief_stages": [...]
  }
}

# Member management with pagination
GET /api/members?page=1&limit=25
POST /api/members
PUT /api/members/{id}

# Care event management
POST /api/care-events
DELETE /api/care-events/{id}  # Auto-recalculates engagement
```

## 🔒 **Security & Permissions**

### **Authentication**
```http
POST /api/auth/login
{
  "email": "admin@gkbj.church",
  "password": "admin123"
}
→ Returns JWT token for API access
```

### **Role Hierarchy**
- **Full Administrator**: All campuses, all features, user management
- **Campus Administrator**: Single campus, user management for campus
- **Pastor**: Pastoral care features for assigned campus

## 📚 **Complete API Documentation**

See `API_DOCUMENTATION.md` for comprehensive endpoint reference including:
- Authentication and user management
- Member CRUD operations with search and pagination
- Care event creation with auto-timeline generation
- Financial aid scheduling with advancement logic
- AI recommendations and analytics endpoints
- Configuration endpoints for mobile app integration

## 🎮 **Testing**

```bash
# Test member search
curl -H "Authorization: Bearer {token}" \
  "http://localhost:8001/api/members?search=sumarni&limit=5"

# Test AI recommendations  
curl -H "Authorization: Bearer {token}" \
  "http://localhost:8001/api/suggestions/follow-up"

# Test configuration (mobile app)
curl "http://localhost:8001/api/config/all"
```

## 📈 **Production Deployment**

### **Docker Deployment**
```dockerfile
# Backend
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

### **Required Services**
- **MongoDB**: Document storage with performance indexes
- **WhatsApp Gateway**: go-whatsapp-web-multidevice at dermapack.net:3001
- **Static hosting**: For frontend deployment (Netlify, Vercel)

## 🎯 **Ready For**

✅ **Production deployment**: Complete enterprise system  
✅ **Mobile app development**: Full API coverage with configuration endpoints  
✅ **Team onboarding**: Comprehensive documentation and guides  
✅ **Daily operations**: 805-member systematic pastoral care management

---

**GKBJ Pastoral Care System - Enterprise solution ensuring no member is left behind!** 🙏

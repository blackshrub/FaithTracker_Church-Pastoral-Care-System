# 🏛️ FaithTracker - Multi-Campus Pastoral Care Management System

**FaithTracker** is a comprehensive, multi-tenant pastoral care management system designed specifically for the GKBJ church. It enables the pastoral care department to efficiently monitor, schedule, and manage all interactions with church members across multiple campuses.

![Status](https://img.shields.io/badge/status-production--ready-brightgreen)
![Platform](https://img.shields.io/badge/platform-FastAPI%20%2B%20React-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
  - [One-Command Installation](#one-command-installation-recommended)
  - [Manual Installation](#manual-installation-optional)
- [Documentation](#documentation)
- [Screenshots](#screenshots)
- [Multi-Language Support](#multi-language-support)
- [Contributing](#contributing)
- [Support](#support)

---

## 🎯 Overview

**FaithTracker** is built to solve the complex challenge of managing pastoral care across multiple church campuses. The system provides:

- **Multi-Tenant Architecture**: Complete data isolation between campuses with role-based access control
- **Task-Oriented Dashboards**: Intelligent task categorization (Today, Overdue, Upcoming)
- **Comprehensive Event Tracking**: Birthdays, grief support, financial aid, hospital visits, and more
- **Smart Scheduling**: Flexible recurring schedules with timezone-aware notifications
- **Member Engagement Monitoring**: Track and visualize member participation over time
- **Bilingual Interface**: Full English and Indonesian (Bahasa Indonesia) support
- **🆕 Global Search**: Lightning-fast member and event search across the app
- **🆕 Complete Accountability**: Track WHO did WHAT on WHICH member (13 action types)
- **🆕 API Sync**: Bi-directional sync with FaithFlow Enterprise (polling + webhooks)
- **🆕 User Management**: Profile photos, edit capabilities, and role management

---

## ✨ Key Features

### 🔐 **Multi-Tenant & Role-Based Access**
- **Full Administrator**: Access all campuses, switch views dynamically
- **Campus Administrator**: Manage a single campus with full control
- **Pastor Role**: Regular pastoral care staff with task management

### 👥 **Member Management**
- Complete CRUD operations for church members
- Photo upload and management
- Family grouping and relationship tracking
- Engagement status monitoring (Active, At Risk, Disconnected)

### 📅 **Care Event System**
- **Birthday Celebrations**: Automated tracking and reminders
- **Grief & Loss Support**: Multi-stage grief care (mourning → 1 year)
- **Financial Aid**: Track and schedule ongoing assistance (education, medical, emergency, housing, food)
- **Hospital Visits**: Accident, illness, and recovery follow-ups
- **Life Events**: New house, childbirth, and other celebrations
- **Regular Contact**: Scheduled check-ins with at-risk members

### 🔔 **Smart Task Management**
- Automatic task generation from events
- Priority-based sorting (overdue → today → upcoming)
- One-click task completion
- "Ignore" functionality for non-applicable tasks
- Clear ignored history per member

### 📊 **Analytics & Reporting**
- Member engagement trends over time
- Event type distribution
- Campus-level statistics
- At-risk member identification

### 🌐 **Import/Export**
- CSV import for bulk member data
- Field mapping for custom CSV formats
- Data export for reporting and backup

### 💬 **WhatsApp Integration** *(Optional)*
- Send reminders via WhatsApp
- Log and track message delivery

---

## 🛠️ Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.9+)
- **Database**: [MongoDB](https://www.mongodb.com/) with Motor (async driver)
- **Authentication**: JWT (JSON Web Tokens) with bcrypt password hashing
- **Scheduling**: APScheduler for background jobs
- **Image Processing**: Pillow

### Frontend
- **Framework**: [React](https://react.dev/) 18+
- **State Management**: [TanStack React Query](https://tanstack.com/query) (for Dashboard & MemberDetail)
- **UI Components**: [Shadcn/UI](https://ui.shadcn.com/) + [Tailwind CSS](https://tailwindcss.com/)
- **Internationalization**: [react-i18next](https://react.i18next.com/)
- **Charts**: Recharts
- **HTTP Client**: Axios

### Infrastructure
- **Process Management**: Supervisord
- **Reverse Proxy**: Nginx
- **OS**: Debian 12 / Ubuntu 20.04+

---

## 🚀 Quick Start

### One-Command Installation (Recommended)

**For a fresh Debian 12 server**, run this single command:

```bash
wget https://raw.githubusercontent.com/YOUR-USERNAME/faithtracker/main/install.sh -O install.sh && chmod +x install.sh && sudo ./install.sh
```

**What the installer does:**
1. ✅ Checks system prerequisites (Python, Node.js, MongoDB, Nginx)
2. ✅ Installs missing dependencies automatically
3. ✅ Clones the repository
4. ✅ Configures environment variables (interactive prompts)
5. ✅ Sets up systemd services for auto-restart
6. ✅ Configures Nginx reverse proxy
7. ✅ Runs smoke tests to verify installation

**Interactive Configuration:**
The installer will prompt you for:
- MongoDB connection string
- JWT secret key (auto-generated if not provided)
- Domain name (for Nginx configuration)
- WhatsApp gateway URL (optional)

**Post-Installation:**
```bash
# Check service status
sudo systemctl status faithtracker-backend
sudo systemctl status nginx

# View logs
sudo journalctl -u faithtracker-backend -f
```

---

### Manual Installation (Optional)

If you prefer to install manually or need customization, follow the **[Detailed Deployment Guide](/docs/DEPLOYMENT_DEBIAN.md)**.

#### Prerequisites
- Python 3.9+
- Node.js 16+ & Yarn
- MongoDB 4.4+
- Nginx

#### Quick Manual Setup

```bash
# 1. Clone repository
git clone https://github.com/YOUR-USERNAME/faithtracker.git
cd faithtracker

# 2. Configure environment
cp .env.example backend/.env
cp .env.example frontend/.env
# Edit both .env files with your configuration

# 3. Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 &

# 4. Frontend setup
cd ../frontend
yarn install
yarn build
# Serve with Nginx or `yarn start` for development
```

For complete step-by-step instructions, see **[/docs/DEPLOYMENT_DEBIAN.md](/docs/DEPLOYMENT_DEBIAN.md)**.

---

## 📚 Documentation

Comprehensive documentation is available in the `/docs` directory:

| Document | Description |
|----------|-------------|
| **[FEATURES.md](/docs/FEATURES.md)** | Detailed feature documentation with user workflows |
| **[API.md](/docs/API.md)** | Complete API endpoint reference with request/response examples |
| **[STRUCTURE.md](/docs/STRUCTURE.md)** | Codebase architecture and file organization |
| **[DEPLOYMENT_DEBIAN.md](/docs/DEPLOYMENT_DEBIAN.md)** | Step-by-step deployment guide for Debian servers |

---

## 📸 Screenshots

### Dashboard (Mobile-First Design)
![Dashboard](docs/images/dashboard.png)
*Task-oriented dashboard with Today, Overdue, and Upcoming tabs*

### Member Detail View
![Member Detail](docs/images/member-detail.png)
*Complete member profile with care event history*

### Analytics
![Analytics](docs/images/analytics.png)
*Member engagement trends and event distribution*

---

## 🌐 Multi-Language Support

FaithTracker is fully internationalized and supports:
- **English (en)**: Complete translation
- **Bahasa Indonesia (id)**: Complete translation

All UI text is externalized in JSON translation files (`/frontend/src/locales/`). Adding a new language is straightforward:

1. Copy `en.json` to `[language-code].json`
2. Translate all strings
3. Update `i18n.js` to include the new language

No code changes required!

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/AmazingFeature`
3. **Commit your changes**: `git commit -m 'Add some AmazingFeature'`
4. **Push to the branch**: `git push origin feature/AmazingFeature`
5. **Open a Pull Request**

### Development Guidelines
- Follow existing code style (Python: PEP 8, JavaScript: ESLint config)
- Write clear commit messages
- Add tests for new features
- Update documentation as needed

---

## 📞 Support

For questions, issues, or feature requests:

- **GitHub Issues**: [github.com/YOUR-USERNAME/faithtracker/issues](https://github.com/YOUR-USERNAME/faithtracker/issues)
- **Email**: support@yourdomain.com
- **Documentation**: Check `/docs` directory first

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built for **GKBJ Church** pastoral care department
- Powered by **FastAPI** and **React**
- UI components by **Shadcn/UI**
- Icons by **Lucide React**

---

**Made with ❤️ for pastoral care excellence**

# \ud83d\udcda FaithTracker Features Documentation

This document provides a comprehensive, user-friendly guide to all features in FaithTracker.

---

## Table of Contents

1. [Multi-Tenant Architecture](#1-multi-tenant-architecture)
2. [Authentication & User Roles](#2-authentication--user-roles)
3. [Dashboard & Task Management](#3-dashboard--task-management)
4. [Member Management](#4-member-management)
5. [Care Event System](#5-care-event-system)
6. [Family Groups](#6-family-groups)
7. [Financial Aid Tracking](#7-financial-aid-tracking)
8. [Analytics & Reporting](#8-analytics--reporting)
9. [Import/Export](#9-importexport)
10. [Settings & Configuration](#10-settings--configuration)
11. [WhatsApp Integration](#11-whatsapp-integration-optional)

---

## 1. Multi-Tenant Architecture

### What is it?
FaithTracker supports **multiple church campuses** in a single installation, with complete data separation between campuses.

### Key Concepts

#### **Campus (Multi-Tenancy)**
- Each campus has its own set of members, events, and care records
- Data is **strictly isolated** - users of Campus A cannot see Campus B's data
- A "Full Administrator" can switch between campus views

#### **Church ID**
- Every member, event, and record is tagged with a `church_id`
- This ensures proper data segregation
- The `church_id` is automatically determined from the logged-in user's campus

### How It Works

**For Full Administrators:**
1. Log in with Full Admin credentials
2. Use the campus selector in the Settings page
3. Switch between different campus views
4. All subsequent operations (viewing, creating, editing) apply to the selected campus

**For Campus Administrators & Pastors:**
- You are permanently assigned to one campus
- You only see data for your campus
- No campus switching available

### Use Cases
- **Multi-campus churches**: Separate pastoral care for downtown, suburban, and satellite campuses
- **Large organizations**: Different departments or regional offices
- **Data privacy**: Ensure each location's data remains private

---

## 2. Authentication & User Roles

### User Roles

FaithTracker has three distinct user roles with different permissions:

| Role | Permissions | Typical Use |
|------|-------------|-------------|
| **Full Administrator** | - Access ALL campuses<br>- Create/edit/delete users<br>- Manage all campuses<br>- Switch campus views | Church leadership, IT administrators |
| **Campus Administrator** | - Manage ONE campus<br>- Create/edit members<br>- Create/edit events<br>- Cannot create other admins | Campus pastor, department head |
| **Pastor** | - View and complete tasks<br>- Add care event notes<br>- Mark tasks as complete<br>- Limited edit permissions | Pastoral care staff, volunteers |

### Login & Registration

**Login:**
1. Navigate to the login page
2. Enter your email and password
3. Click "Login"
4. You'll be redirected to the Dashboard

**Registration (Admin Only):**
- Only **Full Administrators** can create new user accounts
- Navigate to Settings \u2192 Users
- Click "Add New User"
- Fill in:
  - Full name
  - Email address
  - Password
  - Role (Full Admin, Campus Admin, or Pastor)
  - Campus assignment (for Campus Admin and Pastor roles)

### Password Security
- Passwords are hashed using **bcrypt** (industry standard)
- Never stored in plain text
- Minimum length recommended: 8 characters

### Authentication Token (JWT)
- After login, you receive a **JSON Web Token (JWT)**
- Token is valid for **24 hours**
- Automatically refreshed on activity
- Stored securely in browser localStorage

---

## 3. Dashboard & Task Management

The **Dashboard** is the heart of FaithTracker - a task-oriented interface that tells you exactly what needs attention.

### Dashboard Structure

The dashboard uses a **nested 3-tab layout** for mobile-first usability:

#### **Main Tabs**
1. **Tasks**: Your to-do list (Today, Overdue, Upcoming)
2. **Members**: Quick member search and at-risk list
3. **Care Events**: All scheduled care activities

#### **Tasks Tab Sub-Navigation**
- **Today**: Tasks due today (sorted by priority)
- **Overdue**: Past-due tasks requiring immediate attention (highlighted in red)
- **Upcoming**: Future tasks in the next 7 days

### How Tasks Are Generated

Tasks are **automatically created** from care events:
- **Birthday**: Task appears 3 days before the birthday
- **Grief Support**: Tasks appear at each grief stage (1 week, 2 weeks, 1 month, etc.)
- **Financial Aid**: Tasks appear based on the schedule (weekly, monthly, annually)
- **Hospital Visit**: Task appears on the scheduled follow-up date
- **Regular Contact**: Tasks appear based on the recurring schedule

### Task Actions

**Complete a Task:**
1. Click the checkmark (\u2713) button on any task
2. Optionally add a note describing what was done
3. Task is marked complete and removed from active list
4. Logged in the member's care event history

**Ignore a Task:**
- Use when a task is no longer relevant (e.g., member has moved)
- Click "Ignore" button
- Task disappears from your list
- Can be un-ignored from the member detail page

**Send Reminder:**
- Click the "Send Reminder" button (WhatsApp icon)
- Sends a WhatsApp message to the member (if configured)
- Logs the reminder in the system

### Smart Task Sorting

Tasks are intelligently sorted by:
1. **Priority**: Overdue tasks appear first
2. **Date**: Older tasks before newer tasks
3. **Event Type**: Life-critical events (grief, illness) prioritized

---

## 4. Member Management

### Creating a New Member

1. Navigate to **Dashboard \u2192 Members Tab**
2. Click **"Add New Member"** button
3. Fill in the required fields:
   - **Full Name** (required)
   - **Phone Number** (required for WhatsApp)
   - **Email** (optional)
   - **Date of Birth** (for birthday tracking)
   - **Address** (optional)
   - **Family Group** (optional - select existing or create new)
4. Upload a **Photo** (optional but recommended)
5. Click **"Create Member"**

### Viewing Member Details

Click on any member card to view their complete profile:
- **Personal Information**: Name, contact, birthday, address
- **Engagement Status**: Active, At Risk, or Disconnected (auto-calculated)
- **Care Event History**: Timeline of all interactions
- **Upcoming Events**: Future scheduled care activities
- **Family Members**: Other members in the same family group
- **Photos**: Member profile picture

### Editing a Member

1. Open the member detail page
2. Click **"Edit Member"** button
3. Modify any fields
4. Click **"Save Changes"**

### Deleting a Member

1. Open the member detail page
2. Click **"Delete Member"** button
3. Confirm the deletion
4. **Warning**: This also deletes all associated care events and history

### Engagement Status

Members are automatically classified based on recent activity:

- **Active \ud83d\udfe2**: Had a care event in the last 30 days
- **At Risk \ud83d\udfe0**: Last care event was 30-90 days ago
- **Disconnected \ud83d\udd34**: No care event in over 90 days

### Member Photos

**Upload Photo:**
1. Click "Upload Photo" on member detail page
2. Select an image file (JPG, PNG, JPEG, WEBP, HEIC)
3. Image is automatically resized to 800x800px
4. Stored in `/backend/uploads/` directory

**Photo Naming:**
- Format: `JEMAAT-[5-CHARACTER-ID].[ext]`
- Example: `JEMAAT-A1B2C.jpg`

---

## 5. Care Event System

Care events are the core of pastoral care tracking. Each event type has specific workflows.

### Event Types

#### **1. Birthday \ud83c\udf82**
**Purpose**: Celebrate member birthdays with calls or visits

**Workflow:**
1. System automatically detects upcoming birthdays
2. Creates a task 3 days before the birthday
3. Staff completes the task (call, visit, or card sent)
4. Task is marked complete and logged

**Best Practices:**
- Complete birthday tasks on or before the actual birthday
- Add a personal note about the interaction
- Consider sending a card or small gift for long-time members

#### **2. Grief & Loss Support \ud83d\udd4a\ufe0f**
**Purpose**: Provide ongoing support through the stages of grief

**Workflow:**
1. When a member experiences a loss (death of family member, etc.):
   - Create a "Grief/Loss" event
   - Select the grief stage: Mourning, 1 Week, 2 Weeks, 1 Month, 3 Months, 6 Months, 1 Year
2. System creates tasks at each stage
3. Pastor reaches out with appropriate support
4. Mark each stage complete as you provide care

**Grief Stages:**
- **Mourning (0-7 days)**: Immediate support, attend funeral
- **1 Week**: Check-in call
- **2 Weeks**: Visit if possible
- **1 Month**: Phone call or visit
- **3 Months**: Check-in call
- **6 Months**: Visit or meal
- **1 Year**: Memorial acknowledgment

#### **3. Financial Aid \ud83d\udcb5**
**Purpose**: Track and schedule ongoing financial assistance

**Workflow:**
1. Create a "Financial Aid" event
2. Select aid type:
   - Education (tuition, books)
   - Medical (treatment, medication)
   - Emergency (immediate crisis)
   - Housing (rent, mortgage help)
   - Food (groceries, meal support)
   - Funeral Costs
   - Other
3. Set the schedule:
   - **One-Time**: Single payment
   - **Weekly**: Every 7 days
   - **Monthly**: Specific day of month (e.g., 1st, 15th)
   - **Annually**: Once per year
4. System generates tasks based on the schedule
5. When aid is provided, mark the task complete

**Financial Aid Notes:**
- Always document amount and payment method in notes
- Review annually to ensure aid is still needed
- Can "Ignore" future schedules if member's situation improves

#### **4. Hospital Visit / Accident & Illness \ud83c\udfe5**
**Purpose**: Visit and support members during illness or recovery

**Workflow:**
1. Create an "Accident/Illness" event
2. Set the visit date
3. Optionally set follow-up visits (recurring schedule)
4. Complete the visit and log details
5. Continue follow-ups until member recovers

**Best Practices:**
- Visit within 24-48 hours of hospitalization
- Bring prayer, encouragement, and practical help
- Coordinate with family for ongoing needs

#### **5. New House \ud83c\udfe0**
**Purpose**: Celebrate and bless a member's new home

**Workflow:**
1. Create "New House" event
2. Schedule a house blessing or visit
3. Complete the visit
4. Optional: Bring a house-warming gift

#### **6. Childbirth \ud83d\udc76**
**Purpose**: Congratulate and support new parents

**Workflow:**
1. Create "Childbirth" event
2. Schedule initial visit (within 1 week)
3. Optional: Schedule follow-up (1 month, 3 months)
4. Consider: Meal train, baby gift, prayer

#### **7. Regular Contact \ud83d\udcde**
**Purpose**: Maintain ongoing connection with at-risk or isolated members

**Workflow:**
1. Create "Regular Contact" event
2. Set recurring schedule (weekly, bi-weekly, monthly)
3. System generates tasks automatically
4. Staff calls or visits based on schedule
5. Mark each contact complete with notes

**Use Cases:**
- Elderly members living alone
- Members who are "At Risk" or "Disconnected"
- Members with chronic illness or disability
- New members for first-year integration

---

## 6. Family Groups

### What is a Family Group?
A family group links related members together (parents, children, siblings living in the same household).

### Creating a Family Group
1. When creating a member, enter a **Family Group Name** (e.g., "Smith Family")
2. For subsequent family members, select the existing group from the dropdown
3. All members with the same family group are linked

### Benefits
- View all family members from any member's detail page
- Track family-wide events (e.g., new house affects entire family)
- Simplify contact (one address, one household phone)

### Example
**Smith Family:**
- John Smith (father)
- Mary Smith (mother)
- Sarah Smith (daughter)
- David Smith (son)

When viewing John's profile, you see links to Mary, Sarah, and David.

---

## 7. Financial Aid Tracking

### Overview
The financial aid system tracks both **one-time** and **recurring** assistance.

### Creating a Financial Aid Schedule

1. Go to member detail page
2. Click "Add Care Event" \u2192 "Financial Aid"
3. Fill in:
   - **Aid Type**: Education, Medical, Emergency, Housing, Food, Funeral, Other
   - **Amount**: Dollar amount (optional, for notes)
   - **Start Date**: When aid begins
   - **Frequency**:
     - One-Time: Single payment
     - Weekly: Every week
     - Monthly: Day of month (1-31)
     - Annually: Once per year
   - **Notes**: Purpose, account details, etc.
4. Click "Create"

### How Schedules Work

**Weekly:**
- Task appears every 7 days from start date
- Example: Start on January 1 \u2192 tasks on Jan 8, Jan 15, Jan 22, etc.

**Monthly:**
- Task appears on the specified day of each month
- Example: Day 15 \u2192 tasks on 15th of every month
- If the day doesn't exist (e.g., Feb 31), uses last day of month

**Annually:**
- Task appears once per year on the same date
- Example: Start on March 10 \u2192 tasks on March 10 every year

### Completing Aid Tasks
1. Provide the financial assistance
2. Mark the task complete
3. Add a note: "Paid $500 for rent assistance via bank transfer"

### Stopping Aid
If aid is no longer needed:
1. Go to member detail page
2. Find the financial aid event
3. Click "Clear Ignored History" to stop future tasks

---

## 8. Analytics & Reporting

### Overview
The Analytics page provides insights into pastoral care activity and member engagement.

### Key Metrics

**1. Total Members**
- Count of all members in your campus
- Click to view full member list

**2. Active Members**
- Members with care events in the last 30 days
- Green indicator

**3. At-Risk Members**
- Members with last event 30-90 days ago
- Yellow indicator
- Click to view at-risk list

**4. Disconnected Members**
- Members with no event in 90+ days
- Red indicator
- Requires immediate attention

### Charts & Visualizations

**Engagement Trend (Line Chart)**
- Shows active vs. at-risk vs. disconnected members over time
- Time range: Last 6 months
- Helps identify if pastoral care is improving or declining

**Event Type Distribution (Pie Chart)**
- Shows breakdown of care events by type
- Identifies which ministries are most active
- Example: 30% birthdays, 20% grief support, 15% financial aid, etc.

### Using Analytics

**Monthly Review:**
1. Check engagement trend - is the "active" line going up?
2. Review at-risk and disconnected lists
3. Create "Regular Contact" events for disconnected members

**Quarterly Planning:**
1. Review event type distribution
2. Allocate resources to high-volume event types
3. Train staff on most common care scenarios

---

## 9. Import/Export

### CSV Import

**Purpose**: Bulk import members from spreadsheets or other systems

**Steps:**
1. Navigate to **Import/Export** page
2. Prepare your CSV file with columns:
   - `name` or `full_name` (required)
   - `phone` or `phone_number` (required)
   - `email` (optional)
   - `dob` or `date_of_birth` (format: YYYY-MM-DD)
   - `address` (optional)
   - `family_group` (optional)
3. Click **"Choose File"** and select your CSV
4. Review the field mapping:
   - System auto-detects common column names
   - Manually map any unmapped fields
5. Click **"Import"**
6. View import summary (success, errors, duplicates)

**CSV Example:**
```csv
name,phone,email,dob,address,family_group
John Smith,+6281234567890,john@example.com,1980-05-15,123 Main St,Smith Family
Mary Smith,+6281234567891,mary@example.com,1982-08-20,123 Main St,Smith Family
```

### Data Export

**Purpose**: Export data for backup, reporting, or analysis

**Export Options:**
1. **Members**: Full member list with contact info
2. **Care Events**: All care events with dates and notes
3. **Analytics Data**: Engagement statistics

**Steps:**
1. Navigate to **Import/Export** page
2. Select **"Export"** tab
3. Choose export type (Members, Events, or Analytics)
4. Choose format:
   - CSV (for Excel, Google Sheets)
   - JSON (for technical use)
5. Click **"Export"**
6. File downloads automatically

**Use Cases:**
- Weekly backup of member data
- End-of-year report for church leadership
- Transfer data to another system

---

## 10. Settings & Configuration

### User Settings

**Profile:**
- Update your name, email, password
- View your role and campus assignment

**Language:**
- Switch between English and Bahasa Indonesia
- Preference is saved per user

### Admin Settings (Full Admin Only)

**Campus Management:**
1. View all campuses
2. Add new campuses:
   - Campus Name
   - Location
   - Timezone (important for task scheduling!)
3. Edit or delete campuses (warning: deletes all data)

**User Management:**
1. View all users across all campuses
2. Add new users:
   - Full name, email, password
   - Role (Full Admin, Campus Admin, Pastor)
   - Campus assignment
3. Delete users (cannot delete yourself)

**Campus Switching (Full Admin Only):**
1. Go to Settings
2. Select campus from dropdown
3. All views now show data for selected campus

---

## 11. WhatsApp Integration (Optional)

### Overview
FaithTracker can send task reminders via WhatsApp using an external gateway service.

### Setup
1. Set `WHATSAPP_GATEWAY_URL` in backend `.env` file
2. Gateway must accept POST requests with:
   - `to`: Phone number (E.164 format, e.g., +6281234567890)
   - `message`: Text message content
3. System logs all WhatsApp sends in the database

### Sending Reminders
1. From any task, click "Send Reminder" button
2. System sends a message to the member's phone number
3. Message format:
   ```
   Hi [Member Name],
   This is a reminder about [Event Type] on [Date].
   - [Church Name] Pastoral Care
   ```

### Viewing WhatsApp Logs
1. Navigate to **WhatsApp Logs** page
2. View all sent messages with:
   - Timestamp
   - Recipient
   - Message content
   - Delivery status (Sent, Failed, Pending)

### Troubleshooting
- **"WhatsApp not configured"**: Set `WHATSAPP_GATEWAY_URL` in backend `.env`
- **"Failed to send"**: Check gateway URL, network connection, and member phone number format
- **"No phone number"**: Member's phone field is empty - update member profile

---

## Frequently Asked Questions (FAQ)

**Q: Can I delete a task without completing it?**
A: Yes, use the "Ignore" button. It removes the task from your list but logs the action.

**Q: How do I un-ignore a task?**
A: Go to the member's detail page, find the ignored event, and click "Clear Ignored History."

**Q: Can I change a member's campus?**
A: Not directly in the UI. This is a database-level operation. Contact your Full Administrator.

**Q: How often does the engagement status update?**
A: It's calculated in real-time whenever you view a member. Based on the last care event date.

**Q: Can I export data for a specific date range?**
A: Currently, export includes all data. Date range filtering is a planned feature.

**Q: What happens if I delete a member with financial aid schedules?**
A: All associated events and schedules are deleted. Consider marking the member as disconnected instead (future feature).

**Q: Can I customize the grief support stages?**
A: Not currently in the UI. The stages are hard-coded based on pastoral care best practices.

**Q: How do I add a new campus?**
A: Only Full Administrators can do this via Settings \u2192 Campus Management.

---

## Tips & Best Practices

1. **Daily Routine**:
   - Start your day by reviewing "Today" tasks
   - Address "Overdue" tasks first (they're urgent)
   - Plan "Upcoming" tasks for the week

2. **Task Notes**:
   - Always add notes when completing a task
   - Include: what you did, member's response, any follow-up needed
   - These notes create a valuable care history

3. **At-Risk Members**:
   - Review the at-risk list weekly
   - Create "Regular Contact" events for members slipping away
   - Set recurring schedules (monthly check-in calls)

4. **Financial Aid**:
   - Document everything: amounts, dates, reasons
   - Review aid schedules quarterly
   - Stop aid when no longer needed (avoid waste)

5. **Family Groups**:
   - Always assign members to family groups
   - Makes it easier to care for entire families
   - One visit can cover multiple members

6. **Data Hygiene**:
   - Update phone numbers and emails when they change
   - Add photos to member profiles (builds connection)
   - Archive or delete duplicate members

7. **Training New Staff**:
   - Start with "Pastor" role for read-only access
   - Practice completing tasks on test members
   - Upgrade to "Campus Admin" after training

---

**End of Features Documentation**

For technical details, see:
- [API Documentation](/docs/API.md)
- [Codebase Structure](/docs/STRUCTURE.md)
- [Deployment Guide](/docs/DEPLOYMENT_DEBIAN.md)

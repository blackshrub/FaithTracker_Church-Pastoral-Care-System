import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import { Navigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Plus, Trash2, Building2, Users as UsersIcon, Shield } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const AdminDashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [campuses, setCampuses] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Campus form
  const [campusModalOpen, setCampusModalOpen] = useState(false);
  const [newCampus, setNewCampus] = useState({ campus_name: '', location: '' });
  
  // User form
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [newUser, setNewUser] = useState({
    email: '',
    password: '',
    name: '',
    phone: '',
    role: 'pastor',
    campus_id: ''
  });
  
  useEffect(() => {
    if (user?.role === 'full_admin') {
      loadData();
    }
  }, [user]);
  
  const loadData = async () => {
    try {
      setLoading(true);
      const [campusesRes, usersRes] = await Promise.all([
        axios.get(`${API}/campuses`),
        axios.get(`${API}/users`)
      ]);
      setCampuses(campusesRes.data);
      setUsers(usersRes.data);
    } catch (error) {
      toast.error('Failed to load data');
      console.error('Error loading admin data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleAddCampus = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/campuses`, newCampus);
      toast.success('Campus created successfully!');
      setCampusModalOpen(false);
      setNewCampus({ campus_name: '', location: '' });
      loadData();
    } catch (error) {
      toast.error('Failed to create campus');
      console.error('Error creating campus:', error);
    }
  };
  
  const handleAddUser = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/auth/register`, newUser);
      toast.success(`User ${newUser.name} created successfully!`);
      setUserModalOpen(false);
      setNewUser({
        email: '',
        password: '',
        name: '',
        phone: '',
        role: 'pastor',
        campus_id: ''
      });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create user');
      console.error('Error creating user:', error);
    }
  };
  
  const handleDeleteUser = async (userId, userName) => {
    if (!window.confirm(`Delete user ${userName}? This cannot be undone.`)) {
      return;
    }
    
    try {
      await axios.delete(`${API}/users/${userId}`);
      toast.success('User deleted successfully');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete user');
      console.error('Error deleting user:', error);
    }
  };
  
  // Only full admin can access
  if (user?.role !== 'full_admin') {
    return <Navigate to="/dashboard" replace />;
  }
  
  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }
  
  return (
    <div className=\"space-y-6\">
      <div>
        <h1 className=\"text-3xl font-manrope font-bold text-foreground\">Admin Dashboard</h1>
        <p className=\"text-muted-foreground mt-1\">Manage campuses, users, and system settings</p>
      </div>
      
      <Tabs defaultValue=\"campuses\" className=\"w-full\">
        <TabsList className=\"grid w-full grid-cols-2 lg:grid-cols-3\">
          <TabsTrigger value=\"campuses\" data-testid=\"tab-campuses\">
            <Building2 className=\"w-4 h-4 mr-2\" />
            Campuses ({campuses.length})
          </TabsTrigger>
          <TabsTrigger value=\"users\" data-testid=\"tab-users\">
            <UsersIcon className=\"w-4 h-4 mr-2\" />
            Users ({users.length})
          </TabsTrigger>
          <TabsTrigger value=\"settings\" data-testid=\"tab-settings\">
            <Shield className=\"w-4 h-4 mr-2\" />
            Settings
          </TabsTrigger>
        </TabsList>
        
        {/* Campus Management Tab */}
        <TabsContent value=\"campuses\" className=\"space-y-4\">
          <Card>
            <CardHeader>
              <div className=\"flex items-center justify-between\">
                <CardTitle>Campus Management</CardTitle>
                <Dialog open={campusModalOpen} onOpenChange={setCampusModalOpen}>
                  <DialogTrigger asChild>
                    <Button className=\"bg-primary-500 hover:bg-primary-600\" data-testid=\"add-campus-button\">
                      <Plus className=\"w-4 h-4 mr-2\" />
                      Add Campus
                    </Button>
                  </DialogTrigger>
                  <DialogContent data-testid=\"add-campus-modal\">
                    <DialogHeader>
                      <DialogTitle>Add New Campus</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleAddCampus} className=\"space-y-4\">
                      <div className=\"space-y-2\">
                        <Label htmlFor=\"campus_name\">Campus Name *</Label>
                        <Input
                          id=\"campus_name\"
                          value={newCampus.campus_name}
                          onChange={(e) => setNewCampus({...newCampus, campus_name: e.target.value})}
                          placeholder=\"e.g., GKBJ Jakarta Pusat\"
                          required
                          data-testid=\"campus-name-input\"
                        />
                      </div>
                      <div className=\"space-y-2\">
                        <Label htmlFor=\"location\">Location</Label>
                        <Input
                          id=\"location\"
                          value={newCampus.location}
                          onChange={(e) => setNewCampus({...newCampus, location: e.target.value})}
                          placeholder=\"e.g., Jakarta Pusat\"
                          data-testid=\"campus-location-input\"
                        />
                      </div>
                      <div className=\"flex gap-2 justify-end\">
                        <Button type=\"button\" variant=\"outline\" onClick={() => setCampusModalOpen(false)}>
                          Cancel
                        </Button>
                        <Button type=\"submit\" className=\"bg-primary-500 hover:bg-primary-600\" data-testid=\"save-campus-button\">
                          Save Campus
                        </Button>
                      </div>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <div className=\"max-h-[500px] overflow-y-auto\">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Campus Name</TableHead>
                      <TableHead>Location</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className=\"text-right\">Members</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {campuses.map((campus) => (
                      <TableRow key={campus.id} data-testid={`campus-row-${campus.id}`}>
                        <TableCell className=\"font-medium\">{campus.campus_name}</TableCell>
                        <TableCell>{campus.location || '-'}</TableCell>
                        <TableCell>
                          <span className=\"text-xs px-2 py-1 bg-green-100 text-green-700 rounded\">
                            Active
                          </span>
                        </TableCell>
                        <TableCell className=\"text-right\">-</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* User Management Tab */}
        <TabsContent value=\"users\" className=\"space-y-4\">
          <Card>
            <CardHeader>
              <div className=\"flex items-center justify-between\">
                <CardTitle>User Management</CardTitle>
                <Dialog open={userModalOpen} onOpenChange={setUserModalOpen}>
                  <DialogTrigger asChild>
                    <Button className=\"bg-primary-500 hover:bg-primary-600\" data-testid=\"add-user-button\">
                      <Plus className=\"w-4 h-4 mr-2\" />
                      Add User
                    </Button>
                  </DialogTrigger>
                  <DialogContent data-testid=\"add-user-modal\">
                    <DialogHeader>
                      <DialogTitle>Add Pastoral Team Member</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleAddUser} className=\"space-y-4\">
                      <div className=\"space-y-2\">
                        <Label htmlFor=\"user_name\">Name *</Label>
                        <Input
                          id=\"user_name\"
                          value={newUser.name}
                          onChange={(e) => setNewUser({...newUser, name: e.target.value})}
                          placeholder=\"Pastor John\"
                          required
                          data-testid=\"user-name-input\"
                        />
                      </div>
                      <div className=\"space-y-2\">
                        <Label htmlFor=\"user_email\">Email *</Label>
                        <Input
                          id=\"user_email\"
                          type=\"email\"
                          value={newUser.email}
                          onChange={(e) => setNewUser({...newUser, email: e.target.value})}
                          placeholder=\"john@gkbj.church\"
                          required
                          data-testid=\"user-email-input\"
                        />
                      </div>
                      <div className=\"space-y-2\">
                        <Label htmlFor=\"user_phone\">Phone/WhatsApp * (for receiving daily digest)</Label>
                        <Input
                          id=\"user_phone\"
                          value={newUser.phone}
                          onChange={(e) => setNewUser({...newUser, phone: e.target.value})}
                          placeholder=\"628123456789\"
                          required
                          data-testid=\"user-phone-input\"
                        />
                      </div>
                      <div className=\"space-y-2\">
                        <Label htmlFor=\"user_password\">Password *</Label>
                        <Input
                          id=\"user_password\"
                          type=\"password\"
                          value={newUser.password}
                          onChange={(e) => setNewUser({...newUser, password: e.target.value})}
                          placeholder=\"Minimum 8 characters\"
                          required
                          data-testid=\"user-password-input\"
                        />
                      </div>
                      <div className=\"space-y-2\">
                        <Label htmlFor=\"user_role\">Role *</Label>
                        <Select value={newUser.role} onValueChange={(v) => setNewUser({...newUser, role: v})} required>
                          <SelectTrigger data-testid=\"user-role-select\">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value=\"campus_admin\">Campus Admin (manages one campus)</SelectItem>
                            <SelectItem value=\"pastor\">Pastor (pastoral care staff)</SelectItem>
                            <SelectItem value=\"full_admin\">Full Admin (all campuses)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {newUser.role !== 'full_admin' && (
                        <div className=\"space-y-2\">
                          <Label htmlFor=\"user_campus\">Campus * (required for campus admin and pastor)</Label>
                          <Select value={newUser.campus_id} onValueChange={(v) => setNewUser({...newUser, campus_id: v})} required>
                            <SelectTrigger data-testid=\"user-campus-select\">
                              <SelectValue placeholder=\"Select campus\" />
                            </SelectTrigger>
                            <SelectContent className=\"max-h-[200px] overflow-y-auto\">
                              {campuses.map((campus) => (
                                <SelectItem key={campus.id} value={campus.id}>
                                  {campus.campus_name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                      <div className=\"flex gap-2 justify-end\">
                        <Button type=\"button\" variant=\"outline\" onClick={() => setUserModalOpen(false)}>
                          Cancel
                        </Button>
                        <Button type=\"submit\" className=\"bg-primary-500 hover:bg-primary-600\" data-testid=\"save-user-button\">
                          Create User
                        </Button>
                      </div>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Campus</TableHead>
                    <TableHead className=\"text-right\">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
                      <TableCell className=\"font-medium\">{u.name}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>{u.phone}</TableCell>
                      <TableCell>
                        <span className={`text-xs px-2 py-1 rounded font-medium ${
                          u.role === 'full_admin' ? 'bg-purple-100 text-purple-700' :
                          u.role === 'campus_admin' ? 'bg-blue-100 text-blue-700' :
                          'bg-green-100 text-green-700'
                        }`}>
                          {u.role === 'full_admin' ? 'Full Admin' : 
                           u.role === 'campus_admin' ? 'Campus Admin' : 'Pastor'}
                        </span>
                      </TableCell>
                      <TableCell>{u.campus_name || 'All Campuses'}</TableCell>
                      <TableCell className=\"text-right\">
                        {u.id !== user.id && (
                          <Button
                            variant=\"ghost\"
                            size=\"sm\"
                            onClick={() => handleDeleteUser(u.id, u.name)}
                            data-testid={`delete-user-${u.id}`}
                          >
                            <Trash2 className=\"w-4 h-4 text-red-600\" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Settings Tab */}
        <TabsContent value=\"settings\" className=\"space-y-4\">
          <Card>
            <CardHeader>
              <CardTitle>System Settings</CardTitle>
            </CardHeader>
            <CardContent className=\"space-y-4\">
              <div className=\"space-y-2\">
                <Label>Church Name</Label>
                <Input value=\"GKBJ\" disabled />
              </div>
              <div className=\"space-y-2\">
                <Label>WhatsApp Gateway</Label>
                <Input value=\"http://dermapack.net:3001\" disabled />
              </div>
              <div className=\"space-y-2\">
                <Label>Daily Digest Schedule</Label>
                <Input value=\"8:00 AM Jakarta Time\" disabled />
              </div>
              <div className=\"space-y-2\">
                <Label>Database</Label>
                <Input value=\"pastoral_care_db\" disabled />
              </div>
              <div className=\"p-4 bg-blue-50 rounded-lg border border-blue-200\">
                <p className=\"text-sm font-medium text-blue-900\">ℹ️ Daily Digest Behavior</p>
                <p className=\"text-sm text-blue-700 mt-2\">
                  Every day at 8 AM, the system sends a comprehensive task list to all pastoral team members 
                  (campus admins and pastors) via WhatsApp. The digest includes:
                </p>
                <ul className=\"text-sm text-blue-700 mt-2 ml-4 list-disc\">
                  <li>Birthdays today and this week (with phone numbers)</li>
                  <li>Grief support stages due for follow-up</li>
                  <li>Hospital discharge follow-ups needed</li>
                  <li>Members at risk (30+ days no contact)</li>
                </ul>
                <p className=\"text-sm text-blue-700 mt-2\">
                  Pastoral team then <strong>manually and personally contacts each member</strong> via phone or WhatsApp.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminDashboard;

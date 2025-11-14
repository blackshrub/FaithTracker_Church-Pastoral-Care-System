import React, { useState, useEffect } from 'react';
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
  const { user } = useAuth();
  const [campuses, setCampuses] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [campusModalOpen, setCampusModalOpen] = useState(false);
  const [newCampus, setNewCampus] = useState({ campus_name: '', location: '' });
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [newUser, setNewUser] = useState({ email: '', password: '', name: '', phone: '', role: 'pastor', campus_id: '' });
  
  useEffect(() => {
    if (user?.role === 'full_admin') loadData();
  }, [user]);
  
  const loadData = async () => {
    try {
      setLoading(true);
      const [c, u] = await Promise.all([axios.get(`${API}/campuses`), axios.get(`${API}/users`)]);
      setCampuses(c.data);
      setUsers(u.data);
    } catch (error) {
      toast.error('Failed to load');
    } finally {
      setLoading(false);
    }
  };
  
  const handleAddCampus = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/campuses`, newCampus);
      toast.success('Campus created!');
      setCampusModalOpen(false);
      setNewCampus({ campus_name: '', location: '' });
      loadData();
    } catch (error) {
      toast.error('Failed');
    }
  };
  
  const handleAddUser = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/auth/register`, newUser);
      toast.success(`User created!`);
      setUserModalOpen(false);
      setNewUser({ email: '', password: '', name: '', phone: '', role: 'pastor', campus_id: '' });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed');
    }
  };
  
  const handleDeleteUser = async (id, name) => {
    if (!window.confirm(`Delete ${name}?`)) return;
    try {
      await axios.delete(`${API}/users/${id}`);
      toast.success('Deleted');
      loadData();
    } catch (error) {
      toast.error('Failed');
    }
  };
  
  if (user?.role !== 'full_admin') return <Navigate to="/dashboard" />;
  if (loading) return <div>Loading...</div>;
  
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Admin Dashboard</h1>
      <Tabs defaultValue="campuses">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="campuses"><Building2 className="w-4 h-4 mr-2" />Campuses ({campuses.length})</TabsTrigger>
          <TabsTrigger value="users"><UsersIcon className="w-4 h-4 mr-2" />Users ({users.length})</TabsTrigger>
          <TabsTrigger value="settings"><Shield className="w-4 h-4 mr-2" />Settings</TabsTrigger>
        </TabsList>
        
        <TabsContent value="campuses">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Manage Campuses</CardTitle>
                <Dialog open={campusModalOpen} onOpenChange={setCampusModalOpen}>
                  <DialogTrigger asChild>
                    <Button className="bg-teal-500 hover:bg-teal-600 text-white"><Plus className="w-4 h-4 mr-2" />Add Campus</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>Add Campus</DialogTitle></DialogHeader>
                    <form onSubmit={handleAddCampus} className="space-y-4">
                      <div><Label>Campus Name *</Label><Input value={newCampus.campus_name} onChange={(e) => setNewCampus({...newCampus, campus_name: e.target.value})} required /></div>
                      <div><Label>Location</Label><Input value={newCampus.location} onChange={(e) => setNewCampus({...newCampus, location: e.target.value})} /></div>
                      <div className="flex gap-2 justify-end">
                        <Button type="button" variant="outline" onClick={() => setCampusModalOpen(false)}>Cancel</Button>
                        <Button type="submit" className="bg-primary-500">Save</Button>
                      </div>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <div className="max-h-[400px] overflow-y-auto">
                <Table>
                  <TableHeader><TableRow><TableHead>Campus</TableHead><TableHead>Location</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {campuses.map(c => (
                      <TableRow key={c.id}>
                        <TableCell>{c.campus_name}</TableCell>
                        <TableCell>{c.location || '-'}</TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={() => {
                              setNewCampus({campus_name: c.campus_name, location: c.location || ''});
                              setCampusModalOpen(true);
                            }}>Edit</Button>
                            <Button size="sm" variant="ghost" className="text-red-600" onClick={async () => {
                              if (!window.confirm(`Delete ${c.campus_name}?`)) return;
                              try {
                                await axios.delete(`${API}/campuses/${c.id}`);
                                toast.success('Deleted');
                                loadData();
                              } catch (e) {
                                toast.error('Cannot delete - has members');
                              }
                            }}>Delete</Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="users">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Manage Users</CardTitle>
                <Dialog open={userModalOpen} onOpenChange={setUserModalOpen}>
                  <DialogTrigger asChild>
                    <Button className="bg-teal-500 hover:bg-teal-600 text-white"><Plus className="w-4 h-4 mr-2" />Add User</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>Add User</DialogTitle></DialogHeader>
                    <form onSubmit={handleAddUser} className="space-y-3">
                      <div><Label>Name *</Label><Input value={newUser.name} onChange={(e) => setNewUser({...newUser, name: e.target.value})} required /></div>
                      <div><Label>Email *</Label><Input type="email" value={newUser.email} onChange={(e) => setNewUser({...newUser, email: e.target.value})} required /></div>
                      <div><Label>Phone *</Label><Input value={newUser.phone} onChange={(e) => setNewUser({...newUser, phone: e.target.value})} required /></div>
                      <div><Label>Password *</Label><Input type="password" value={newUser.password} onChange={(e) => setNewUser({...newUser, password: e.target.value})} required /></div>
                      <div><Label>Role *</Label>
                        <Select value={newUser.role} onValueChange={(v) => setNewUser({...newUser, role: v})}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="campus_admin">Campus Admin</SelectItem>
                            <SelectItem value="pastor">Pastor</SelectItem>
                            <SelectItem value="full_admin">Full Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {newUser.role !== 'full_admin' && (
                        <div><Label>Campus *</Label>
                          <Select value={newUser.campus_id} onValueChange={(v) => setNewUser({...newUser, campus_id: v})}>
                            <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                            <SelectContent className="max-h-[200px] overflow-y-auto">
                              {campuses.map(c => <SelectItem key={c.id} value={c.id}>{c.campus_name}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                      <div className="flex gap-2 justify-end">
                        <Button type="button" variant="outline" onClick={() => setUserModalOpen(false)}>Cancel</Button>
                        <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white">Create</Button>
                      </div>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Phone</TableHead><TableHead>Role</TableHead><TableHead>Campus</TableHead><TableHead>Actions</TableHead></TableRow></TableHeader>
                <TableBody>
                  {users.map(u => (
                    <TableRow key={u.id}>
                      <TableCell>{u.name}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>{u.phone}</TableCell>
                      <TableCell>
                        <span className={`text-xs px-2 py-1 rounded ${u.role === 'full_admin' ? 'bg-purple-100 text-purple-700' : u.role === 'campus_admin' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                          {u.role === 'full_admin' ? 'Full Admin' : u.role === 'campus_admin' ? 'Campus Admin' : 'Pastor'}
                        </span>
                      </TableCell>
                      <TableCell>{u.campus_name || 'All'}</TableCell>
                      <TableCell>
                        {u.id !== user.id && <Button variant="ghost" size="sm" onClick={() => handleDeleteUser(u.id, u.name)}><Trash2 className="w-4 h-4 text-red-600" /></Button>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="settings">
          <div className="space-y-6">
            <Card>
              <CardHeader><CardTitle>Recalculate Engagement Status</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Recalculate engagement status for all members using current threshold settings (At-Risk: 60 days, Disconnected: 90 days).
                    This is useful after changing engagement thresholds or when deploying to production.
                  </p>
                  <Button 
                    onClick={async () => {
                      if (window.confirm('Recalculate engagement status for all members? This may take a few seconds.')) {
                        const loadingToast = toast.loading('Recalculating engagement status for all members...');
                        try {
                          const response = await axios.post(`${API}/admin/recalculate-engagement`, {}, {
                            timeout: 60000 // 60 second timeout
                          });
                          toast.dismiss(loadingToast);
                          toast.success(`✅ Updated ${response.data.updated_count} members!\nActive: ${response.data.stats.active}, At-Risk: ${response.data.stats.at_risk}, Disconnected: ${response.data.stats.disconnected}`);
                          loadStats();
                        } catch (error) {
                          toast.dismiss(loadingToast);
                          // Check if it's a timeout but actually succeeded
                          if (error.code === 'ECONNABORTED') {
                            toast.success('Recalculation started! Please refresh the page in a few seconds to see updated counts.');
                          } else {
                            toast.error('Failed to recalculate engagement status');
                          }
                        }
                      }
                    }}
                    className="bg-teal-500 hover:bg-teal-600 text-white"
                  >
                    Recalculate All Members
                  </Button>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Daily Digest System</CardTitle></CardHeader>
              <CardContent>
                <div className="p-4 bg-blue-50 rounded-lg">
                  <p className="font-medium">📋 How It Works:</p>
                  <p className="text-sm mt-2">Every day at 8 AM Jakarta time, pastoral team receives WhatsApp with task list: birthdays, grief support, hospital follow-ups, at-risk members. Team then personally contacts each member.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminDashboard;

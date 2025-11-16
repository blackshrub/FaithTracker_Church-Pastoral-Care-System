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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { Plus, Trash2, Building2, Users as UsersIcon, Shield, MoreVertical } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const AdminDashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [campuses, setCampuses] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [campusModalOpen, setCampusModalOpen] = useState(false);
  const [newCampus, setNewCampus] = useState({ id: null, campus_name: '', location: '' });
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
      toast.error(t('toasts.failed_load'));
    } finally {
      setLoading(false);
    }
  };
  
  const handleAddCampus = async (e) => {
    e.preventDefault();
    try {
      if (newCampus.id) {
        // Update existing campus
        await axios.put(`${API}/campuses/${newCampus.id}`, { campus_name: newCampus.campus_name, location: newCampus.location });
        toast.success(t('toasts.campus_updated'));
      } else {
        // Create new campus
        await axios.post(`${API}/campuses`, newCampus);
        toast.success(t('toasts.campus_created'));
      }
      setCampusModalOpen(false);
      setNewCampus({ id: null, campus_name: '', location: '' });
      loadData();
    } catch (error) {
      toast.error(t('toasts.failed'));
    }
  };
  
  const handleAddUser = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/auth/register`, newUser);
      toast.success(t('admin_dashboard.user_created'));
      setUserModalOpen(false);
      setNewUser({ email: '', password: '', name: '', phone: '', role: 'pastor', campus_id: '' });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toasts.failed'));
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
  if (loading) return <div className="max-w-full">Loading...</div>;
  
  return (
    <div className="space-y-6 max-w-full">
      <h1 className="text-3xl font-playfair font-bold">Admin Dashboard</h1>
      <Tabs defaultValue="campuses" className="max-w-full">
        <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex w-full justify-center">
            <TabsTrigger value="campuses" className="flex-shrink-0"><Building2 className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Campuses</span> ({campuses.length})</TabsTrigger>
            <TabsTrigger value="users" className="flex-shrink-0"><UsersIcon className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Users</span> ({users.length})</TabsTrigger>
            <TabsTrigger value="settings" className="flex-shrink-0"><Shield className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Settings</span></TabsTrigger>
          </TabsList>
        </div>
        
        <TabsContent value="campuses">
          <Card className="max-w-full overflow-hidden">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Manage Campuses</CardTitle>
                <Dialog open={campusModalOpen} onOpenChange={setCampusModalOpen}>
                  <DialogTrigger asChild>
                    <Button className="bg-teal-500 hover:bg-teal-600 text-white"><Plus className="w-4 h-4 mr-2" />Add Campus</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>{newCampus.id ? 'Edit Campus' : 'Add Campus'}</DialogTitle></DialogHeader>
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
            <CardContent className="p-4">
              {/* Mobile Card Layout */}
              <div className="block sm:hidden space-y-3">
                {campuses.map(c => (
                  <div key={c.id} className="p-4 border border-gray-200 rounded-lg bg-white shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm">{c.campus_name}</p>
                        <p className="text-xs text-muted-foreground mt-1">{c.location || '-'}</p>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0 flex-shrink-0">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-32">
                          <DropdownMenuItem onClick={() => {
                            setNewCampus({id: c.id, campus_name: c.campus_name, location: c.location || ''});
                            setCampusModalOpen(true);
                          }}>
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem 
                            className="text-red-600"
                            onClick={async () => {
                              if (!window.confirm(`Delete ${c.campus_name}?`)) return;
                              try {
                                await axios.delete(`${API}/campuses/${c.id}`);
                                toast.success('Deleted');
                                loadData();
                              } catch (e) {
                                toast.error('Cannot delete - has members');
                              }
                            }}
                          >
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Desktop Table Layout */}
              <div className="hidden sm:block overflow-x-auto">
                <Table className="w-full">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-2 pr-1">Campus</TableHead>
                      <TableHead className="hidden sm:table-cell">Location</TableHead>
                      <TableHead className="w-10 text-center px-1">⋮</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {campuses.map(c => (
                      <TableRow key={c.id}>
                        <TableCell className="pl-2 pr-1">
                          <div>
                            <p className="font-medium text-sm">{c.campus_name}</p>
                            <p className="text-xs text-muted-foreground sm:hidden">{c.location || '-'}</p>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">{c.location || '-'}</TableCell>
                        <TableCell className="w-10 text-center px-1">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-32">
                              <DropdownMenuItem onClick={() => {
                                setNewCampus({id: c.id, campus_name: c.campus_name, location: c.location || ''});
                                setCampusModalOpen(true);
                              }}>
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem 
                                className="text-red-600"
                                onClick={async () => {
                                  if (!window.confirm(`Delete ${c.campus_name}?`)) return;
                                  try {
                                    await axios.delete(`${API}/campuses/${c.id}`);
                                    toast.success('Deleted');
                                    loadData();
                                  } catch (e) {
                                    toast.error('Cannot delete - has members');
                                  }
                                }}
                              >
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
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
          <Card className="max-w-full overflow-hidden">
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
                          <SelectTrigger className="h-12"><SelectValue /></SelectTrigger>
                          <SelectContent position="popper" sideOffset={5}>
                            <SelectItem value="campus_admin">Campus Admin</SelectItem>
                            <SelectItem value="pastor">Pastor</SelectItem>
                            <SelectItem value="full_admin">Full Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {newUser.role !== 'full_admin' && (
                        <div><Label>Campus *</Label>
                          <Select value={newUser.campus_id} onValueChange={(v) => setNewUser({...newUser, campus_id: v})}>
                            <SelectTrigger className="h-12"><SelectValue placeholder="Select" /></SelectTrigger>
                            <SelectContent position="popper" sideOffset={5} className="max-h-[200px] overflow-y-auto">
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
            <CardContent className="p-4">
              {/* Mobile Card Layout */}
              <div className="block sm:hidden space-y-3">
                {users.map(u => (
                  <div key={u.id} className="p-4 border border-gray-200 rounded-lg bg-white shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm">{u.name}</p>
                        <p className="text-xs text-muted-foreground mt-1">{u.email}</p>
                        <span className={`inline-block text-xs px-2 py-1 rounded mt-2 ${u.role === 'full_admin' ? 'bg-purple-100 text-purple-700' : u.role === 'campus_admin' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                          {u.role === 'full_admin' ? 'Full Admin' : u.role === 'campus_admin' ? 'Campus Admin' : 'Pastor'}
                        </span>
                      </div>
                      {u.id !== user.id && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 flex-shrink-0">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-32">
                            <DropdownMenuItem 
                              className="text-red-600"
                              onClick={() => handleDeleteUser(u.id, u.name)}
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Desktop Table Layout */}
              <div className="hidden sm:block overflow-x-auto">
                <Table className="w-full">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-2 pr-1">Name</TableHead>
                      <TableHead className="hidden md:table-cell">Email</TableHead>
                      <TableHead className="px-1">Role</TableHead>
                      <TableHead className="w-10 text-center px-1">⋮</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map(u => (
                      <TableRow key={u.id}>
                        <TableCell className="pl-2 pr-1">
                          <div>
                            <p className="font-medium text-sm">{u.name}</p>
                            <p className="text-xs text-muted-foreground md:hidden">{u.email}</p>
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">{u.email}</TableCell>
                        <TableCell className="px-1">
                          <span className={`text-xs px-2 py-1 rounded whitespace-nowrap ${u.role === 'full_admin' ? 'bg-purple-100 text-purple-700' : u.role === 'campus_admin' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                            {u.role === 'full_admin' ? 'Full Admin' : u.role === 'campus_admin' ? 'Campus Admin' : 'Pastor'}
                          </span>
                        </TableCell>
                        <TableCell className="w-10 text-center px-1">
                          {u.id !== user.id && (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                  <MoreVertical className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-32">
                                <DropdownMenuItem 
                                  className="text-red-600"
                                  onClick={() => handleDeleteUser(u.id, u.name)}
                                >
                                  <Trash2 className="w-4 h-4 mr-2" />
                                  Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
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
                      if (window.confirm('Recalculate engagement status for all 805 members? This process runs in the background and may take 10-15 seconds.')) {
                        try {
                          // Fire the request (don't wait for response due to long processing time)
                          axios.post(`${API}/admin/recalculate-engagement`, {}, {
                            timeout: 90000
                          }).catch(() => {
                            // Ignore timeout errors - backend still processing
                          });
                          
                          toast.success('✅ Recalculation started! Please wait 15 seconds then refresh the page to see updated counts.', {
                            duration: 8000
                          });
                        } catch (error) {
                          toast.error('Failed to start recalculation');
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

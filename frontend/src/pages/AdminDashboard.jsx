import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import { Navigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { Plus, Trash2, Building2, Users as UsersIcon, Shield, MoreVertical, Edit, Phone } from 'lucide-react';

export const AdminDashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [campusModalOpen, setCampusModalOpen] = useState(false);
  const [newCampus, setNewCampus] = useState({ id: null, campus_name: '', location: '' });
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);

  // Use TanStack Query for data fetching with prefetched cache from route loader
  const { data: adminData, isLoading: loading, refetch: loadData } = useQuery({
    queryKey: ['admin-data'],
    queryFn: async () => {
      const [c, u] = await Promise.all([api.get('/campuses'), api.get('/users')]);
      return { campuses: c.data || [], users: u.data || [] };
    },
    staleTime: 1000 * 60 * 5, // 5 minutes - data is fresh for longer
    gcTime: 1000 * 60 * 10, // 10 minutes - keep in cache longer
  });

  const campuses = adminData?.campuses || [];
  const users = adminData?.users || [];

  const [confirmDialog, setConfirmDialog] = useState({
    open: false,
    title: '',
    description: '',
    onConfirm: () => {}
  });

  const showConfirm = (title, description, onConfirm) => {
    setConfirmDialog({ open: true, title, description, onConfirm });
  };

  const closeConfirm = () => {
    setConfirmDialog({ open: false, title: '', description: '', onConfirm: () => {} });
  };

  const [newUser, setNewUser] = useState({ email: '', password: '', name: '', phone: '', role: 'pastor', campus_id: '' });
  
  const handleAddCampus = async (e) => {
    e.preventDefault();
    try {
      if (newCampus.id) {
        // Update existing campus
        await api.put(`/campuses/${newCampus.id}`, { campus_name: newCampus.campus_name, location: newCampus.location });
        toast.success(t('toasts.campus_updated'));
      } else {
        // Create new campus
        await api.post(`/campuses`, newCampus);
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
      await api.post(`/auth/register`, newUser);
      toast.success(t('admin_dashboard_page.user_created'));
      setUserModalOpen(false);
      setNewUser({ email: '', password: '', name: '', phone: '', role: 'pastor', campus_id: '' });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toasts.failed'));
    }
  };
  
  const handleDeleteUser = async (id, name) => {
    showConfirm(
      'Delete User',
      `Are you sure you want to delete ${name}? This action cannot be undone.`,
      async () => {
        try {
          await api.delete(`/users/${id}`);
          toast.success(t('toasts.deleted'));
          loadData();
          closeConfirm();
        } catch (error) {
          toast.error(t('toasts.failed'));
          closeConfirm();
        }
      }
    );
  };

  const handleEditUser = (userToEdit) => {
    setEditingUser(userToEdit);
    setNewUser({
      email: userToEdit.email,
      password: '', // Don't show existing password
      name: userToEdit.name,
      phone: userToEdit.phone || '',
      role: userToEdit.role,
      campus_id: userToEdit.campus_id || ''
    });
    setUserModalOpen(true);
  };
  
  const handleUpdateUser = async (e) => {
    e.preventDefault();
    try {
      const updateData = {
        name: newUser.name,
        phone: newUser.phone,
        role: newUser.role,
        campus_id: newUser.campus_id || null
      };
      
      // Only include password if changed
      if (newUser.password && newUser.password.trim()) {
        updateData.password = newUser.password;
      }
      
      await api.put(`/users/${editingUser.id}`, updateData);
      toast.success(t('User updated successfully'));
      setUserModalOpen(false);
      setEditingUser(null);
      setNewUser({ email: '', password: '', name: '', phone: '', role: 'pastor', campus_id: '' });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update user');
    }
  };
  
  const closeUserModal = () => {
    setUserModalOpen(false);
    setEditingUser(null);
    setNewUser({ email: '', password: '', name: '', phone: '', role: 'pastor', campus_id: '' });
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
                <CardTitle>{t('admin_dashboard_page.manage_campuses')}</CardTitle>
                <Dialog open={campusModalOpen} onOpenChange={setCampusModalOpen}>
                  <DialogTrigger asChild>
                    <Button className="bg-teal-500 hover:bg-teal-600 text-white"><Plus className="w-4 h-4 mr-2" />{t('admin_dashboard_page.add_campus')}</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>{newCampus.id ? t('admin_dashboard_page.edit_campus') : t('admin_dashboard_page.add_campus')}</DialogTitle></DialogHeader>
                    <form onSubmit={handleAddCampus} className="space-y-4">
                      <div><Label>{t('admin_dashboard_page.campus_name')}</Label><Input value={newCampus.campus_name} onChange={(e) => setNewCampus({...newCampus, campus_name: e.target.value})} required /></div>
                      <div><Label>{t('admin_dashboard_page.location')}</Label><Input value={newCampus.location} onChange={(e) => setNewCampus({...newCampus, location: e.target.value})} /></div>
                      <div className="flex gap-2 justify-end">
                        <Button type="button" variant="outline" onClick={() => setCampusModalOpen(false)}>{t('cancel')}</Button>
                        <Button type="submit" className="bg-primary-500">{t('admin_dashboard_page.save')}</Button>
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
                              showConfirm(
                                'Delete Campus',
                                `Delete ${c.campus_name}? This will also delete all members and data for this campus.`,
                                async () => {
                                  try {
                                    await api.delete(`/campuses/${c.id}`);
                                    toast.success(t('toasts.deleted'));
                                    loadData();
                                    closeConfirm();
                                  } catch (e) {
                                    toast.error(t('toasts.cannot_delete_has_members'));
                                    closeConfirm();
                                  }
                                }
                              );
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
                                  showConfirm(
                                    'Delete Campus',
                                    `Delete ${c.campus_name}? This will also delete all members and data for this campus.`,
                                    async () => {
                                      try {
                                        await api.delete(`/campuses/${c.id}`);
                                        toast.success(t('toasts.deleted'));
                                        loadData();
                                        closeConfirm();
                                      } catch (e) {
                                        toast.error(t('toasts.cannot_delete_has_members'));
                                        closeConfirm();
                                      }
                                    }
                                  );
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
                <CardTitle>{t('admin_dashboard_page.manage_users')}</CardTitle>
                <Dialog open={userModalOpen} onOpenChange={(open) => { if (!open) closeUserModal(); else setUserModalOpen(open); }}>
                  <DialogTrigger asChild>
                    <Button className="bg-teal-500 hover:bg-teal-600 text-white"><Plus className="w-4 h-4 mr-2" />{t('admin_dashboard_page.add_user')}</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>{editingUser ? 'Edit User' : t('admin_dashboard_page.add_user')}</DialogTitle></DialogHeader>
                    <form onSubmit={editingUser ? handleUpdateUser : handleAddUser} className="space-y-3">
                      <div><Label>{t('admin_dashboard_page.name_required')}</Label><Input value={newUser.name} onChange={(e) => setNewUser({...newUser, name: e.target.value})} required /></div>
                      <div><Label>{t('admin_dashboard_page.email_required')}</Label><Input type="email" value={newUser.email} onChange={(e) => setNewUser({...newUser, email: e.target.value})} required disabled={editingUser} /></div>
                      <div><Label>{t('admin_dashboard_page.phone_required')}</Label><Input value={newUser.phone} onChange={(e) => setNewUser({...newUser, phone: e.target.value})} placeholder="081234567890" /></div>
                      <div><Label>{editingUser ? 'Password (leave blank to keep current)' : t('admin_dashboard_page.password_required')}</Label><Input type="password" value={newUser.password} onChange={(e) => setNewUser({...newUser, password: e.target.value})} required={!editingUser} /></div>
                      <div><Label>{t('admin_dashboard_page.role_required')}</Label>
                        <Select value={newUser.role} onValueChange={(v) => setNewUser({...newUser, role: v})}>
                          <SelectTrigger className="h-12"><SelectValue /></SelectTrigger>
                          <SelectContent position="popper" sideOffset={5}>
                            <SelectItem value="campus_admin">{t('admin_dashboard_page.role_campus_admin')}</SelectItem>
                            <SelectItem value="pastor">{t('admin_dashboard_page.role_pastor')}</SelectItem>
                            <SelectItem value="full_admin">{t('admin_dashboard_page.role_full_admin')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {newUser.role !== 'full_admin' && (
                        <div><Label>{t('admin_dashboard_page.campus_required')}</Label>
                          <Select value={newUser.campus_id} onValueChange={(v) => setNewUser({...newUser, campus_id: v})}>
                            <SelectTrigger className="h-12"><SelectValue placeholder={t('misc.select')} /></SelectTrigger>
                            <SelectContent position="popper" sideOffset={5} className="max-h-[200px] overflow-y-auto">
                              {campuses.map(c => <SelectItem key={c.id} value={c.id}>{c.campus_name}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                      <div className="flex gap-2 justify-end">
                        <Button type="button" variant="outline" onClick={closeUserModal}>{t('cancel')}</Button>
                        <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white">{editingUser ? 'Update' : t('admin_dashboard_page.create')}</Button>
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
                      <TableHead className="hidden lg:table-cell">Phone</TableHead>
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
                            <p className="text-xs text-muted-foreground lg:hidden">{u.phone}</p>
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">{u.email}</TableCell>
                        <TableCell className="hidden lg:table-cell">{u.phone || '-'}</TableCell>
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
                                <DropdownMenuItem onClick={() => handleEditUser(u)}>
                                  <Edit className="w-4 h-4 mr-2" />
                                  Edit
                                </DropdownMenuItem>
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
              <CardHeader><CardTitle>{t('admin_dashboard_page.recalculate_engagement')}</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    {t('admin_dashboard_page.recalculate_description')}
                  </p>
                  <Button 
                    onClick={() => {
                      showConfirm(
                        'Recalculate Engagement',
                        t('admin_dashboard_page.recalculate_confirm'),
                        async () => {
                          try {
                            // Fire the request (don't wait for response due to long processing time)
                            api.post(`/admin/recalculate-engagement`, {}, {
                              timeout: 90000
                            }).catch(() => {
                              // Ignore timeout errors - backend still processing
                            });
                            
                            toast.success(t('admin_dashboard_page.recalculation_started'), {
                              duration: 8000
                            });
                            closeConfirm();
                          } catch (error) {
                            toast.error(t('admin_dashboard_page.failed_start_recalculation'));
                            closeConfirm();
                          }
                        }
                      );
                    }}
                    className="bg-teal-500 hover:bg-teal-600 text-white"
                  >
                    {t('admin_dashboard_page.recalculate_button')}
                  </Button>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>{t('admin_dashboard_page.daily_digest_system')}</CardTitle></CardHeader>
              <CardContent>
                <div className="p-4 bg-blue-50 rounded-lg">
                  <p className="font-medium">{t('admin_dashboard_page.digest_how_it_works')}</p>
                  <p className="text-sm mt-2">{t('admin_dashboard_page.digest_explanation')}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
      
      <ConfirmDialog
        open={confirmDialog.open}
        onOpenChange={(open) => !open && closeConfirm()}
        title={confirmDialog.title}
        description={confirmDialog.description}
        onConfirm={confirmDialog.onConfirm}
        onCancel={closeConfirm}
      />
    </div>
  );
};

export default AdminDashboard;

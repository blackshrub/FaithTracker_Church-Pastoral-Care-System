import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { MemberLink } from '@/components/LinkWithPrefetch';
import { useDebounce } from 'use-debounce';
import api from '@/lib/api';
import { formatDate } from '@/lib/dateUtils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { MembersListSkeleton } from '@/components/skeletons';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Plus, Search, Loader2 } from 'lucide-react';
import { MemberAvatar } from '@/components/MemberAvatar';
import { EngagementBadge } from '@/components/EngagementBadge';
import { ErrorState } from '@/components/ErrorState';
import { EmptyMembers, EmptySearch } from '@/components/EmptyState';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const MembersList = () => {
  const { t } = useTranslation();
  const [members, setMembers] = useState([]);

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

  const [allMembers, setAllMembers] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalMembers, setTotalMembers] = useState(0);
  const [pageSize] = useState(25); // Industry standard: 25 items per page
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false); // Separate table loading
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebounce(search, 600); // 600ms debounce for responsive UX
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchLoading, setSearchLoading] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [loadError, setLoadError] = useState(null);
  
  const handleSearchKeyDown = (e) => {
    if (e.key === 'Enter' && search.length >= 1) {
      setCurrentPage(1);
      loadMembers(1, search);
    }
  };
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState(null);
  const [selectedMembers, setSelectedMembers] = useState([]);
  const [saving, setSaving] = useState(false);
  // Available columns config - will be filtered based on actual member data
  const allPossibleColumns = {
    phone: { label: 'Phone', field: 'phone' },
    age: { label: 'Age', field: 'age' },
    gender: { label: 'Gender', field: 'gender' },
    membership_status: { label: 'Membership', field: 'membership_status' },
    marital_status: { label: 'Marital', field: 'marital_status' },
    category: { label: 'Category', field: 'category' },
    blood_type: { label: 'Blood Type', field: 'blood_type' },
    address: { label: 'Address', field: 'address' },
    birth_date: { label: 'Birth Date', field: 'birth_date' },
    engagement: { label: 'Engagement', field: 'engagement_status' }
  };

  // Track which columns have data (at least one member has this field)
  const [availableColumns, setAvailableColumns] = useState([]);
  const [visibleColumns, setVisibleColumns] = useState({});
  
  const [newMember, setNewMember] = useState({
    name: '',
    phone: '',
    notes: ''
  });

  useEffect(() => {
    loadMembers(currentPage);
  }, [currentPage, debouncedSearch, filterStatus, showArchived]);

  useEffect(() => {
    // Reset to page 1 when search/filter changes
    setCurrentPage(1);
  }, [debouncedSearch, filterStatus]);
  
  const loadMembers = async (page = 1, searchQuery = null) => {
    try {
      setLoadError(null); // Clear any previous errors
      // Use tableLoading for pagination/search, loading for initial load only
      if (currentPage > 0) {
        setTableLoading(true);
      } else {
        setLoading(true);
      }
      
      // Use provided search query or debounced search
      const activeSearch = searchQuery !== null ? searchQuery : debouncedSearch;
      
      // Build query parameters properly
      const params = new URLSearchParams();
      params.append('page', page.toString());
      params.append('limit', pageSize.toString());
      
      // Allow single character search (minimum 1 character)
      if (activeSearch && activeSearch.trim().length >= 1) {
        params.append('search', activeSearch.trim());
      }
      
      if (filterStatus && filterStatus !== 'all') {
        // Only add engagement_status if it's a valid value
        const validStatuses = ['active', 'at_risk', 'disconnected'];
        if (validStatuses.includes(filterStatus)) {
          params.append('engagement_status', filterStatus);
        }
      }
      
      // Add archived filter
      if (showArchived) {
        params.append('show_archived', 'true');
      }
      
      const response = await api.get(`/members?${params.toString()}`);
      const membersData = response.data || [];
      setMembers(membersData);
      setSearchLoading(false); // Clear search loading

      // Detect which columns have data from the first batch of members
      if (membersData.length > 0 && availableColumns.length === 0) {
        const columnsWithData = [];
        const initialVisibility = {};

        Object.entries(allPossibleColumns).forEach(([key, config]) => {
          // Check if any member has this field with a non-empty value
          const hasData = membersData.some(m => {
            const value = m[config.field];
            return value !== null && value !== undefined && value !== '';
          });

          if (hasData) {
            columnsWithData.push(key);
            initialVisibility[key] = true; // Show all available columns by default
          }
        });

        setAvailableColumns(columnsWithData);
        setVisibleColumns(initialVisibility);
      }

      // Get total count from header and calculate pages
      const total = parseInt(response.headers['x-total-count'] || '0', 10);
      setTotalMembers(total);
      setTotalPages(Math.ceil(total / pageSize));
      setCurrentPage(page);
    } catch (error) {
      setSearchLoading(false); // Clear loading on error too
      setLoadError(error);
      toast.error(t('error_messages.failed_to_save'));
      console.error('Error loading members:', error);
    } finally {
      setLoading(false);
      setTableLoading(false);
    }
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      loadMembers(newPage);
    }
  };
  
  const handleAddMember = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post(`/members`, {...newMember, campus_id: 'auto'});
      toast.success(t('success_messages.member_created'));
      setAddModalOpen(false);
      setNewMember({ name: '', phone: '', notes: '' });
      loadMembers();
    } catch (error) {
      toast.error(t('error_messages.failed_to_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleEditMember = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.put(`/members/${editingMember.id}`, editingMember);
      toast.success('Member updated!');
      setEditModalOpen(false);
      setEditingMember(null);
      loadMembers();
    } catch (error) {
      toast.error('Failed to update');
    } finally {
      setSaving(false);
    }
  };
  
  const handleDeleteMember = async (id, name) => {
    showConfirm(
      'Delete Member',
      `Delete ${name}? This will also delete all care events and history for this member.`,
      async () => {
        try {
          await api.delete(`/members/${id}`);
          toast.success('Member deleted');
          loadMembers();
          closeConfirm();
        } catch (error) {
          toast.error('Failed to delete member');
          closeConfirm();
        }
      }
    );
  };
  
  const handleBulkDelete = async () => {
    if (selectedMembers.length === 0) return;
    showConfirm(
      'Delete Selected Members',
      `Delete ${selectedMembers.length} members? This will delete all their care events and history.`,
      async () => {
        try {
          await Promise.all(selectedMembers.map(id => api.delete(`/members/${id}`)));
          toast.success(`Deleted ${selectedMembers.length} members`);
          setSelectedMembers([]);
          loadMembers();
          closeConfirm();
        } catch (error) {
          toast.error('Failed to delete members');
          closeConfirm();
        }
      }
    );
  };
  
  const toggleSelectMember = (id) => {
    setSelectedMembers(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };
  
  const toggleSelectAll = () => {
    if (selectedMembers.length === filteredMembers.length) {
      setSelectedMembers([]);
    } else {
      setSelectedMembers(filteredMembers.map(m => m.id));
    }
  };
  
  const filteredMembers = members.filter(member => {
    const matchesSearch = member.name.toLowerCase().includes(search.toLowerCase()) ||
                         member.phone.includes(search);
    const matchesStatus = filterStatus === 'all' || member.engagement_status === filterStatus;
    return matchesSearch && matchesStatus;
  });
  
  if (loading) {
    return <MembersListSkeleton />;
  }

  if (loadError) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <ErrorState error={loadError} onRetry={() => loadMembers(currentPage)} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-3xl font-playfair font-bold text-foreground">{t('members')}</h1>
          <p className="text-muted-foreground mt-1">{totalMembers} total members</p>
        </div>
        
        <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
          <DialogTrigger asChild>
            <Button className="bg-teal-500 hover:bg-teal-600 text-white h-12 min-w-0" data-testid="open-add-member-modal">
              <Plus className="w-4 h-4 mr-2 flex-shrink-0" />
              <span className="truncate">{t('add_member')}</span>
            </Button>
          </DialogTrigger>
          <DialogContent data-testid="add-member-modal">
            <DialogHeader>
              <DialogTitle>{t('add_member')}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleAddMember} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">{t('member_name')} *</Label>
                <Input
                  id="name"
                  value={newMember.name}
                  onChange={(e) => setNewMember({...newMember, name: e.target.value})}
                  required
                  data-testid="member-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">{t('phone_number')} *</Label>
                <Input
                  id="phone"
                  value={newMember.phone}
                  onChange={(e) => setNewMember({...newMember, phone: e.target.value})}
                  placeholder="628123456789"
                  required
                  data-testid="member-phone-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="notes">{t('notes')}</Label>
                <Input
                  id="notes"
                  value={newMember.notes}
                  onChange={(e) => setNewMember({...newMember, notes: e.target.value})}
                  data-testid="member-notes-input"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={() => setAddModalOpen(false)} disabled={saving}>
                  {t('cancel')}
                </Button>
                <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white" loading={saving} data-testid="save-member-button">
                  {t('save')}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>

        {/* Edit Member Modal */}
        <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
          <DialogContent data-testid="edit-member-modal">
            <DialogHeader>
              <DialogTitle>{t('edit_member')}</DialogTitle>
            </DialogHeader>
            {editingMember && (
              <form onSubmit={handleEditMember} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="edit_name">{t('member_name')} *</Label>
                  <Input
                    id="edit_name"
                    value={editingMember.name}
                    onChange={(e) => setEditingMember({...editingMember, name: e.target.value})}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_phone">{t('phone_number')} *</Label>
                  <Input
                    id="edit_phone"
                    value={editingMember.phone}
                    onChange={(e) => setEditingMember({...editingMember, phone: e.target.value})}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_notes">{t('notes')}</Label>
                  <Input
                    id="edit_notes"
                    value={editingMember.notes || ''}
                    onChange={(e) => setEditingMember({...editingMember, notes: e.target.value})}
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <Button type="button" variant="outline" onClick={() => setEditModalOpen(false)} disabled={saving}>
                    {t('cancel')}
                  </Button>
                  <Button type="submit" className="bg-teal-500 hover:bg-teal-600" loading={saving}>
                    {t('save')}
                  </Button>
                </div>
              </form>
            )}
          </DialogContent>
        </Dialog>
      </div>
      
      {/* Filters and Column Visibility */}
      <Card className="border-border max-w-full">
        <CardContent className="p-4">
          <div className="flex flex-col gap-4 max-w-full">
            <div className="flex flex-col md:flex-row gap-4 max-w-full">
              <div className="flex-1 min-w-0">
                <div className="relative">
                  {searchLoading ? (
                    <Loader2 className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-teal-500 animate-spin" />
                  ) : (
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  )}
                  <Input
                    placeholder="Type name or phone to search"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      if (e.target.value.length >= 1) {
                        setSearchLoading(true);
                      }
                    }}
                    onKeyDown={handleSearchKeyDown}
                    className="pl-10 h-12"
                    data-testid="search-members-input"
                  />
                </div>
              </div>
              <div className="flex gap-2 flex-shrink-0">
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-full md:w-48 h-12" data-testid="filter-status-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('members_list.all_status')}</SelectItem>
                    <SelectItem value="active">{t('active')}</SelectItem>
                    <SelectItem value="at_risk">{t('at_risk')}</SelectItem>
                    <SelectItem value="disconnected">{t('disconnected')}</SelectItem>
                  </SelectContent>
                </Select>
                <Button 
                  variant={showArchived ? "default" : "outline"}
                  onClick={() => {
                    setShowArchived(!showArchived);
                    setCurrentPage(1);
                  }}
                  className="whitespace-nowrap"
                >
                  {showArchived ? '👁️ Showing Archived' : '📁 Show Archived'}
                </Button>
              </div>
            </div>
            
            {/* Column Visibility Toggles - Only show columns that have data */}
            {availableColumns.length > 0 && (
              <div className="border-t pt-4">
                <p className="text-sm font-semibold mb-2">{t('members_list.show_columns')}</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 sm:gap-3">
                  {availableColumns.map((key) => (
                    <label key={key} className="flex items-center gap-2 cursor-pointer min-w-0">
                      <input
                        type="checkbox"
                        checked={visibleColumns[key] || false}
                        onChange={(e) => setVisibleColumns({...visibleColumns, [key]: e.target.checked})}
                        className="w-4 h-4 flex-shrink-0"
                      />
                      <span className="text-sm truncate">{allPossibleColumns[key]?.label || key}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
      
      {/* Members Table */}
      <Card className="border-border shadow-sm">
        {selectedMembers.length > 0 && (
          <div className="p-4 bg-amber-50 border-b flex items-center justify-between">
            <span className="font-semibold">{selectedMembers.length} members selected</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setSelectedMembers([])}>{t('members_list.clear_selection')}</Button>
              <Button size="sm" variant="destructive" onClick={handleBulkDelete}>{t('members_list.delete_selected')}</Button>
            </div>
          </div>
        )}
        <CardContent className="p-0 relative">
          {tableLoading && (
            <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex items-center justify-center">
              <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 text-teal-500 animate-spin" />
                <span className="text-sm text-teal-700">{t('members_list.loading_members')}</span>
              </div>
            </div>
          )}
          <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12 hidden sm:table-cell">
                    <input type="checkbox" checked={selectedMembers.length === filteredMembers.length && filteredMembers.length > 0} onChange={toggleSelectAll} className="w-4 h-4" />
                  </TableHead>
                  <TableHead>{t('members_list.name')}</TableHead>
                  {/* Dynamic columns based on visibility settings */}
                  {availableColumns.filter(col => visibleColumns[col]).map(col => (
                    <TableHead key={col} className="hidden md:table-cell">
                      {allPossibleColumns[col]?.label || col}
                    </TableHead>
                  ))}
                  <TableHead className="text-right">{t('members_list.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tableLoading || (search && search !== debouncedSearch) ? (
                  <TableRow>
                    <TableCell colSpan={3 + availableColumns.filter(col => visibleColumns[col]).length} className="text-center py-8">
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-teal-500" />
                        <span className="text-muted-foreground">{t('members_list.searching_members')}</span>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : filteredMembers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3 + availableColumns.filter(col => visibleColumns[col]).length} className="py-0">
                      {search ? (
                        <EmptySearch searchTerm={search} />
                      ) : (
                        <EmptyMembers onAddMember={() => setAddModalOpen(true)} />
                      )}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredMembers.map((member) => (
                    <TableRow key={member.id} className="hover:bg-muted/50 transition-colors">
                      <TableCell className="hidden sm:table-cell">
                        <input type="checkbox" checked={selectedMembers.includes(member.id)} onChange={() => toggleSelectMember(member.id)} className="w-4 h-4" />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <MemberAvatar member={member} size="sm" />
                          <span className="font-medium">{member.name}</span>
                        </div>
                      </TableCell>
                      {/* Dynamic column cells based on visibility settings */}
                      {availableColumns.filter(col => visibleColumns[col]).map(col => {
                        const field = allPossibleColumns[col]?.field || col;
                        let value = member[field];

                        // Special rendering for certain columns
                        if (col === 'engagement') {
                          return (
                            <TableCell key={col} className="hidden md:table-cell">
                              <EngagementBadge status={member.engagement_status} days={member.days_since_last_contact} />
                            </TableCell>
                          );
                        }
                        if (col === 'birth_date' && value) {
                          value = formatDate(value);
                        }

                        return (
                          <TableCell key={col} className="hidden md:table-cell">
                            {value || '-'}
                          </TableCell>
                        );
                      })}
                      <TableCell className="text-right">
                        <div className="flex gap-1 justify-end">
                          <MemberLink memberId={member.id}>
                            <Button size="sm" variant="outline">{t('view')}</Button>
                          </MemberLink>
                          <Button size="sm" variant="ghost" className="hidden sm:inline-flex" onClick={() => { setEditingMember(member); setEditModalOpen(true); }}>{t('edit')}</Button>
                          <Button size="sm" variant="ghost" className="text-red-600 hidden sm:inline-flex" onClick={() => handleDeleteMember(member.id, member.name)}>{t('delete')}</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
      
      {/* Industry-Standard Pagination Controls */}
      <div className="flex items-center justify-between mt-6">
        <div className="text-sm text-muted-foreground">
          Showing {totalMembers > 0 ? ((currentPage - 1) * pageSize) + 1 : 0}-{Math.min(currentPage * pageSize, totalMembers)} of {totalMembers} members
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage <= 1}
          >
            Previous
          </Button>
          
          {/* Page Numbers */}
          <div className="flex gap-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const page = Math.max(1, currentPage - 2) + i;
              if (page > totalPages) return null;
              return (
                <Button
                  key={page}
                  variant={currentPage === page ? "default" : "outline"}
                  size="sm"
                  className={currentPage === page ? "bg-teal-500 text-white" : ""}
                  onClick={() => handlePageChange(page)}
                >
                  {page}
                </Button>
              );
            })}
          </div>
          
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
          >
            Next
          </Button>
        </div>
      </div>

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

export default MembersList;
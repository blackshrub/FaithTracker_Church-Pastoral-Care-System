import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useDebounce } from 'use-debounce';
import { FixedSizeList as List } from 'react-window';
import axios from 'axios';
import { format } from 'date-fns';

// Safe date formatter
const formatDate = (dateStr, formatStr = 'dd MMM yyyy') => {
  try {
    return format(new Date(dateStr), formatStr);
  } catch (e) {
    return dateStr;
  }
};
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Plus, Search } from 'lucide-react';
import { MemberAvatar } from '@/components/MemberAvatar';
import { EngagementBadge } from '@/components/EngagementBadge';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const MembersList = () => {
  const { t } = useTranslation();
  const [members, setMembers] = useState([]);
  const [familyGroups, setFamilyGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebounce(search, 300); // 300ms debounce
  const [filterStatus, setFilterStatus] = useState('all');
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState(null);
  const [selectedMembers, setSelectedMembers] = useState([]);
  const [visibleColumns, setVisibleColumns] = useState({
    phone: true,
    age: true,
    gender: true,
    membership: true,
    marital: true,
    category: true,
    blood_type: true,
    family: true,
    last_contact: true,
    engagement: true
  });
  
  const [newMember, setNewMember] = useState({
    name: '',
    phone: '',
    family_group_name: '',
    notes: ''
  });
  
  useEffect(() => {
    loadMembers();
    loadFamilyGroups();
  }, []);
  
  const loadMembers = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/members`);
      setMembers(response.data);
    } catch (error) {
      toast.error(t('error_messages.failed_to_save'));
      console.error('Error loading members:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadFamilyGroups = async () => {
    try {
      const response = await axios.get(`${API}/family-groups`);
      setFamilyGroups(response.data);
    } catch (error) {
      console.error('Error loading family groups:', error);
    }
  };
  
  const handleAddMember = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/members`, {...newMember, campus_id: 'auto'});
      toast.success(t('success_messages.member_created'));
      setAddModalOpen(false);
      setNewMember({ name: '', phone: '', family_group_name: '', notes: '' });
      loadMembers();
      loadFamilyGroups();
    } catch (error) {
      toast.error(t('error_messages.failed_to_save'));
    }
  };
  
  const handleEditMember = async (e) => {
    e.preventDefault();
    try {
      await axios.put(`${API}/members/${editingMember.id}`, editingMember);
      toast.success('Member updated!');
      setEditModalOpen(false);
      setEditingMember(null);
      loadMembers();
    } catch (error) {
      toast.error('Failed to update');
    }
  };
  
  const handleDeleteMember = async (id, name) => {
    if (!window.confirm(`Delete ${name}?`)) return;
    try {
      await axios.delete(`${API}/members/${id}`);
      toast.success('Member deleted');
      loadMembers();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };
  
  const handleBulkDelete = async () => {
    if (selectedMembers.length === 0) return;
    if (!window.confirm(`Delete ${selectedMembers.length} members?`)) return;
    
    try {
      await Promise.all(selectedMembers.map(id => axios.delete(`${API}/members/${id}`)));
      toast.success(`${selectedMembers.length} members deleted`);
      setSelectedMembers([]);
      loadMembers();
    } catch (error) {
      toast.error('Bulk delete failed');
    }
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
  
  // Memoized row component for virtual scrolling
  const MemberRow = React.memo(({ index, style }) => {
    const member = filteredMembers[index];
    if (!member) return null;

    return (
      <div style={style} className="border-b border-border">
        <div className="flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors">
          <input
            type="checkbox"
            checked={selectedMembers.includes(member.id)}
            onChange={() => toggleSelectMember(member.id)}
            className="w-4 h-4"
          />
          <div className="flex items-center gap-3 flex-1">
            <MemberAvatar member={member} size="sm" />
            <div>
              <span className="font-medium">{member.name}</span>
              <p className="text-sm text-muted-foreground">{member.phone || '-'}</p>
            </div>
          </div>
          <div className="text-sm">{member.age || '-'}</div>
          <div className="text-sm">{member.gender || '-'}</div>
          <EngagementBadge status={member.engagement_status} days={member.days_since_last_contact} />
          <div className="flex gap-1">
            <Link to={`/members/${member.id}`}>
              <Button size="sm" variant="outline">View</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  });
    return members.filter(member => {
      const matchesSearch = member.name.toLowerCase().includes(debouncedSearch.toLowerCase()) ||
                           member.phone.includes(debouncedSearch);
      const matchesStatus = filterStatus === 'all' || member.engagement_status === filterStatus;
      return matchesSearch && matchesStatus;
    });
  }, [members, debouncedSearch, filterStatus]);
  
  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-manrope font-bold text-foreground">{t('members')}</h1>
          <p className="text-muted-foreground mt-1">{members.length} total members</p>
        </div>
        
        <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
          <DialogTrigger asChild>
            <Button className="bg-teal-500 hover:bg-teal-600 text-white" data-testid="open-add-member-modal">
              <Plus className="w-4 h-4 mr-2" />
              {t('add_member')}
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
                <Label htmlFor="family_group">{t('family_group')}</Label>
                <Input
                  id="family_group"
                  value={newMember.family_group_name}
                  onChange={(e) => setNewMember({...newMember, family_group_name: e.target.value})}
                  placeholder="Enter new family group name"
                  data-testid="family-group-input"
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
                <Button type="button" variant="outline" onClick={() => setAddModalOpen(false)}>
                  {t('cancel')}
                </Button>
                <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white" data-testid="save-member-button">
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
                  <Button type="button" variant="outline" onClick={() => setEditModalOpen(false)}>
                    {t('cancel')}
                  </Button>
                  <Button type="submit" className="bg-teal-500 hover:bg-teal-600">
                    {t('save')}
                  </Button>
                </div>
              </form>
            )}
          </DialogContent>
        </Dialog>
      </div>
      
      {/* Filters and Column Visibility */}
      <Card className="border-border">
        <CardContent className="p-4">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder={t('search')}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-10"
                    data-testid="search-members-input"
                  />
                </div>
              </div>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-full md:w-48" data-testid="filter-status-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">{t('active')}</SelectItem>
                  <SelectItem value="at_risk">{t('at_risk')}</SelectItem>
                  <SelectItem value="inactive">{t('inactive')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Column Visibility Toggles */}
            <div className="border-t pt-4">
              <p className="text-sm font-semibold mb-2">Show Columns:</p>
              <div className="flex flex-wrap gap-3">
                {Object.entries({
                  phone: 'Phone', age: 'Age', gender: 'Gender', membership: 'Membership',
                  marital: 'Marital', category: 'Category', blood_type: 'Blood Type',
                  family: 'Family', last_contact: 'Last Contact', engagement: 'Engagement'
                }).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={visibleColumns[key]}
                      onChange={(e) => setVisibleColumns({...visibleColumns, [key]: e.target.checked})}
                      className="w-4 h-4"
                    />
                    <span className="text-sm">{label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Virtual Scrolled Members Table */}
      <Card className="border-border shadow-sm">
        {selectedMembers.length > 0 && (
          <div className="p-4 bg-amber-50 border-b flex items-center justify-between">
            <span className="font-semibold">{selectedMembers.length} members selected</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setSelectedMembers([])}>Clear Selection</Button>
              <Button size="sm" variant="destructive" onClick={handleBulkDelete}>Delete Selected</Button>
            </div>
          </div>
        )}
        <CardContent className="p-0">
          <div className="p-4 border-b bg-muted/30">
            <div className="flex items-center gap-4 font-semibold text-sm">
              <input type="checkbox" checked={selectedMembers.length === filteredMembers.length && filteredMembers.length > 0} onChange={toggleSelectAll} className="w-4 h-4" />
              <span className="flex-1">Member</span>
              <span className="w-20">Age</span>
              <span className="w-20">Gender</span>
              <span className="w-32">Status</span>
              <span className="w-24">Actions</span>
            </div>
          </div>
          <List
            height={600}
            itemCount={filteredMembers.length}
            itemSize={80}
            itemData={filteredMembers}
          >
            {MemberRow}
          </List>
        </CardContent>
      </Card>
    </div>
  );
};

export default MembersList;
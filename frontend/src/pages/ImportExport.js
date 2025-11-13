import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Upload, Download, FileJson, FileSpreadsheet } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const ImportExport = () => {
  const { user } = useAuth();
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [syncInterval, setSyncInterval] = useState(60);
  const [selectedCampusId, setSelectedCampusId] = useState('');
  const [campuses, setCampuses] = useState([]);
  const [fieldMapping, setFieldMapping] = useState({
    name: 'name',
    phone: 'phone',
    email: 'email',
    external_id: 'id',
    birth_date: 'birth_date',
    category: 'category',
    gender: 'gender',
    blood_type: 'blood_type',
    marital_status: 'marital_status',
    membership_status: 'membership_status',
    address: 'address'
  });
  const [activeSyncs, setActiveSyncs] = useState([]);
  const [importing, setImporting] = useState(false);
  
  useEffect(() => {
    loadCampuses();
    loadActiveSyncs();
  }, []);
  
  const loadCampuses = async () => {
    try {
      const response = await axios.get(`${API}/campuses`);
      setCampuses(response.data);
      if (response.data.length > 0) {
        setSelectedCampusId(response.data[0].id);
      }
    } catch (error) {
      console.error('Error loading campuses');
    }
  };
  
  const loadActiveSyncs = async () => {
    // Mock data for now - would load from backend in production
    setActiveSyncs([
      {
        id: '1',
        name: 'Main Church System',
        url: 'https://church-system.com/api/members',
        interval: 60,
        last_sync: new Date(),
        status: 'active',
        campus_name: 'GKBJ Taman Kencana'
      }
    ]);
  };
  
  const handleCsvImport = async (e) => {
    e.preventDefault();
    if (!csvFile) return;
    
    try {
      setImporting(true);
      const formData = new FormData();
      formData.append('file', csvFile);
      
      const response = await axios.post(`${API}/import/members/csv`, formData);
      toast.success(`Imported ${response.data.imported_count} members!`);
      if (response.data.errors.length > 0) {
        toast.warning(`${response.data.errors.length} errors occurred`);
      }
      setCsvFile(null);
    } catch (error) {
      toast.error('Import failed');
    } finally {
      setImporting(false);
    }
  };
  
  const handleJsonImport = async (e) => {
    e.preventDefault();
    try {
      setImporting(true);
      const members = JSON.parse(jsonData);
      const response = await axios.post(`${API}/import/members/json`, members);
      toast.success(`Imported ${response.data.imported_count} members!`);
      setJsonData('');
    } catch (error) {
      toast.error('Import failed - check JSON format');
    } finally {
      setImporting(false);
    }
  };
  
  const handleApiSync = async (e) => {
    e.preventDefault();
    if (!apiUrl) return;
    
    try {
      setImporting(true);
      const response = await axios.post(`${API}/sync/members/from-api`, null, {
        params: { api_url: apiUrl, api_key: apiKey || undefined }
      });
      toast.success(`Synced ${response.data.synced_count} members from API!`);
      if (response.data.errors.length > 0) {
        toast.warning(`${response.data.errors.length} errors occurred`);
      }
      setApiUrl('');
      setApiKey('');
    } catch (error) {
      toast.error('API sync failed');
    } finally {
      setImporting(false);
    }
  };
  
  const handleExportMembers = async () => {
    try {
      const response = await axios.get(`${API}/export/members/csv`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `members_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Members exported!');
    } catch (error) {
      toast.error('Export failed');
    }
  };
  
  const handleExportEvents = async () => {
    try {
      const response = await axios.get(`${API}/export/care-events/csv`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `care_events_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Events exported!');
    } catch (error) {
      toast.error('Export failed');
    }
  };
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Import/Export Data</h1>
        <p className="text-muted-foreground mt-1">Sync member data and export reports</p>
      </div>
      
      <Tabs defaultValue="import">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="import"><Upload className="w-4 h-4 mr-2" />Import</TabsTrigger>
          <TabsTrigger value="export"><Download className="w-4 h-4 mr-2" />Export</TabsTrigger>
        </TabsList>
        
        <TabsContent value="import" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>CSV Import</CardTitle>
              <CardDescription>Upload CSV file to bulk import members</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCsvImport} className="space-y-4">
                <div>
                  <Label>Select CSV File</Label>
                  <Input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files[0])} />
                  <p className="text-xs text-muted-foreground mt-1">Required columns: name, phone</p>
                </div>
                <Button type="submit" disabled={!csvFile || importing}>
                  <FileSpreadsheet className="w-4 h-4 mr-2" />
                  {importing ? 'Importing...' : 'Import CSV'}
                </Button>
              </form>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>JSON Import</CardTitle>
              <CardDescription>Paste JSON array for API integration</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleJsonImport} className="space-y-4">
                <div>
                  <Label>JSON Data</Label>
                  <textarea 
                    className="w-full h-32 p-2 border rounded" 
                    value={jsonData}
                    onChange={(e) => setJsonData(e.target.value)}
                    placeholder='[{"name": "John Doe", "phone": "628xxx"}]'
                  />
                </div>
                <Button type="submit" disabled={!jsonData || importing}>
                  <FileJson className="w-4 h-4 mr-2" />
                  {importing ? 'Importing...' : 'Import JSON'}
                </Button>
              </form>
            </CardContent>
          </Card>
          
          <Card className="card-border-left-teal">
            <CardHeader>
              <CardTitle>API Sync (Continuous)</CardTitle>
              <CardDescription>Connect to external church management system for continuous sync</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleApiSync} className="space-y-4">
                <div>
                  <Label>External API URL *</Label>
                  <Input
                    value={apiUrl}
                    onChange={(e) => setApiUrl(e.target.value)}
                    placeholder="https://your-church-system.com/api/members"
                    required
                  />
                </div>
                <div>
                  <Label>API Key (optional)</Label>
                  <Input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Bearer token if required"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Sync Interval (minutes) *</Label>
                    <Input
                      type="number"
                      value={syncInterval}
                      onChange={(e) => setSyncInterval(parseInt(e.target.value))}
                      min="1"
                      placeholder="60"
                    />
                    <p className="text-xs text-muted-foreground">Auto-sync every X minutes</p>
                  </div>
                  <div>
                    <Label>Assign to Campus *</Label>
                    <Select value={selectedCampusId} onValueChange={setSelectedCampusId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select campus" />
                      </SelectTrigger>
                      <SelectContent>
                        {campuses.map(campus => (
                          <SelectItem key={campus.id} value={campus.id}>{campus.campus_name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-3">
                  <Label className="font-semibold">Field Mapping (map your API fields to our system)</Label>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries({
                      name: 'Name Field',
                      phone: 'Phone Field', 
                      email: 'Email Field',
                      external_id: 'ID Field',
                      birth_date: 'Birthday Field',
                      category: 'Category Field',
                      gender: 'Gender Field',
                      blood_type: 'Blood Type Field',
                      marital_status: 'Marital Field',
                      membership_status: 'Membership Field',
                      address: 'Address Field'
                    }).map(([key, label]) => (
                      <div key={key}>
                        <Label className="text-xs">{label}:</Label>
                        <Input
                          value={fieldMapping[key]}
                          onChange={(e) => setFieldMapping({...fieldMapping, [key]: e.target.value})}
                          placeholder={key}
                          className="text-sm"
                        />
                      </div>
                    ))}
                  </div>
                </div>
                <Button type="submit" disabled={!apiUrl || importing} className="bg-teal-500 hover:bg-teal-600 text-white">
                  <FileJson className="w-4 h-4 mr-2" />
                  {importing ? 'Syncing...' : 'Create Sync Job'}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="export" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Export Members</CardTitle>
              <CardDescription>Download all members as CSV</CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={handleExportMembers}>
                <Download className="w-4 h-4 mr-2" />
                Export Members CSV
              </Button>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Export Care Events</CardTitle>
              <CardDescription>Download all care events as CSV</CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={handleExportEvents}>
                <Download className="w-4 h-4 mr-2" />
                Export Events CSV
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ImportExport;
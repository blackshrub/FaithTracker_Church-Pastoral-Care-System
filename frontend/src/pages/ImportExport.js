import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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
    address: 'address',
    photo_url: 'photo_url'
  });
  const [activeSyncs, setActiveSyncs] = useState([]);
  const [importing, setImporting] = useState(false);
  const [csvFile, setCsvFile] = useState(null);
  const [jsonData, setJsonData] = useState('');
  const [csvPreview, setCsvPreview] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [validationResults, setValidationResults] = useState(null);
  const [apiPreview, setApiPreview] = useState(null);
  const [showApiPreview, setShowApiPreview] = useState(false);
  const [apiValidation, setApiValidation] = useState(null);
  const [editingSyncId, setEditingSyncId] = useState(null);
  const [editSyncOpen, setEditSyncOpen] = useState(false);
  
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
  
  const handleEditSync = (syncId) => {
    const sync = activeSyncs.find(s => s.id === syncId);
    if (sync) {
      setApiUrl(sync.url);
      setSyncInterval(sync.interval);
      setEditingSyncId(syncId);
      setEditSyncOpen(true);
    }
  };
  
  const handleUpdateSync = async (e) => {
    e.preventDefault();
    // Would update sync job in backend
    toast.success('Sync job updated!');
    setEditSyncOpen(false);
    setEditingSyncId(null);
    loadActiveSyncs();
  };
  
  const handleCsvSelect = async (e) => {
    const file = e.target.files[0];
    setCsvFile(file);
    
    if (file) {
      // Parse CSV for preview
      const text = await file.text();
      const lines = text.split('\n').filter(line => line.trim());
      if (lines.length > 0) {
        const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
        const preview = lines.slice(1, 11).map(line => {
          const values = line.split(',').map(v => v.replace(/"/g, '').trim());
          const row = {};
          headers.forEach((h, i) => row[h] = values[i] || '');
          return row;
        });
        
        // Validate required fields
        const requiredFields = ['name', 'phone'];
        const hasRequired = requiredFields.every(field => 
          headers.some(h => h.toLowerCase().includes(field.toLowerCase()))
        );
        
        setCsvPreview({ headers, preview, total: lines.length - 1 });
        setValidationResults({
          hasRequired,
          missingFields: requiredFields.filter(field => 
            !headers.some(h => h.toLowerCase().includes(field.toLowerCase()))
          )
        });
        setShowPreview(true);
      }
    }
  };
  const handleCsvImport = async () => {
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
      setShowPreview(false);
      setCsvPreview(null);
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
  
  const handleApiTest = async () => {
    if (!apiUrl) {
      toast.error('Enter API URL first');
      return;
    }
    
    try {
      setImporting(true);
      // Test API connection and get preview data
      const headers = apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {};
      const response = await axios.get(apiUrl, { headers, timeout: 10000 });
      const data = Array.isArray(response.data) ? response.data : [response.data];
      
      if (data.length === 0) {
        toast.error('API returned no data');
        return;
      }
      
      // Validate field mapping
      const sample = data[0];
      const mappingValid = {};
      const mappingErrors = [];
      
      Object.entries(fieldMapping).forEach(([ourField, theirField]) => {
        const hasField = sample.hasOwnProperty(theirField);
        mappingValid[ourField] = hasField;
        if (!hasField && ['name', 'phone'].includes(ourField)) {
          mappingErrors.push(`Required field "${theirField}" not found in API response`);
        }
      });
      
      // Check data quality
      const qualityIssues = [];
      data.slice(0, 10).forEach((item, i) => {
        const name = item[fieldMapping.name];
        const phone = item[fieldMapping.phone];
        
        if (!name) qualityIssues.push(`Row ${i+1}: Missing name`);
        if (!phone) qualityIssues.push(`Row ${i+1}: Missing phone`);
        if (phone && !phone.match(/^(\+?62|0)[0-9]{8,13}$/)) {
          qualityIssues.push(`Row ${i+1}: Invalid phone format (${phone})`);
        }
      });
      
      setApiPreview(data.slice(0, 10));
      setApiValidation({
        success: true,
        total: data.length,
        mappingValid,
        mappingErrors,
        qualityIssues: qualityIssues.slice(0, 10) // Show first 10 issues
      });
      setShowApiPreview(true);
      toast.success('API connection successful!');
      
    } catch (error) {
      setApiValidation({
        success: false,
        error: error.response?.data?.message || error.message || 'API connection failed'
      });
      setShowApiPreview(true);
      toast.error('API connection failed');
    } finally {
      setImporting(false);
    }
  };
  
  const handleApiSyncConfirm = async () => {
    if (!window.confirm(`Create API sync job?\n\nThis will sync ${apiValidation.total} members every ${syncInterval} minutes from ${selectedCampusId ? campuses.find(c => c.id === selectedCampusId)?.campus_name : 'selected campus'}.`)) {
      return;
    }
    
    try {
      setImporting(true);
      const response = await axios.post(`${API}/sync/members/from-api`, null, {
        params: { api_url: apiUrl, api_key: apiKey || undefined }
      });
      toast.success(`API sync created! ${response.data.synced_count} members synced.`);
      if (response.data.errors.length > 0) {
        toast.warning(`${response.data.errors.length} errors occurred`);
      }
      setApiUrl('');
      setApiKey('');
      setShowApiPreview(false);
      setApiPreview(null);
      loadActiveSyncs();
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="import"><Upload className="w-4 h-4 mr-2" />Import</TabsTrigger>
          <TabsTrigger value="export"><Download className="w-4 h-4 mr-2" />Export</TabsTrigger>
          <TabsTrigger value="sync-status">🔄 API Sync Status</TabsTrigger>
        </TabsList>
        
        <TabsContent value="import" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>CSV Import</CardTitle>
              <CardDescription>Upload CSV file to bulk import members</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <Label>Select CSV File</Label>
                  <Input type="file" accept=".csv" onChange={handleCsvSelect} />
                  <p className="text-xs text-muted-foreground mt-1">Required columns: name, phone</p>
                </div>
                
                {showPreview && csvPreview && (
                  <div className="space-y-4 p-4 border rounded bg-blue-50">
                    <h4 className="font-semibold">📋 CSV Preview & Validation</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm font-medium">File Info:</p>
                        <p className="text-sm text-muted-foreground">{csvPreview.total} rows to import</p>
                        <p className="text-sm text-muted-foreground">{csvPreview.headers.length} columns detected</p>
                      </div>
                      <div>
                        <p className="text-sm font-medium">Validation:</p>
                        {validationResults?.hasRequired ? (
                          <p className="text-sm text-green-600">✅ Required fields found</p>
                        ) : (
                          <p className="text-sm text-red-600">❌ Missing: {validationResults?.missingFields.join(', ')}</p>
                        )}
                      </div>
                    </div>
                    
                    <div className="max-h-48 overflow-auto border rounded bg-white p-2">
                      <table className="w-full text-xs">
                        <thead>
                          <tr>{csvPreview.headers.map(h => <th key={h} className="border p-1 text-left">{h}</th>)}</tr>
                        </thead>
                        <tbody>
                          {csvPreview.preview.slice(0, 5).map((row, i) => (
                            <tr key={i}>
                              {csvPreview.headers.map(h => <td key={h} className="border p-1">{row[h] || '-'}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    
                    {validationResults?.hasRequired ? (
                      <Button 
                        onClick={async () => {
                          if (window.confirm(`Import ${csvPreview.total} members? This will update existing and create new members.`)) {
                            await handleCsvImport();
                          }
                        }}
                        className="bg-teal-500 hover:bg-teal-600 text-white"
                      >
                        ✅ Confirm Import ({csvPreview.total} members)
                      </Button>
                    ) : (
                      <p className="text-red-600 text-sm">Cannot import - missing required fields</p>
                    )}
                  </div>
                )}
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
                      address: 'Address Field',
                      photo_url: 'Photo URL Field'
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
                <Button type="button" disabled={!apiUrl || importing} className="bg-blue-500 hover:bg-blue-600 text-white" onClick={handleApiTest}>
                  {importing ? 'Testing...' : 'Test API Connection'}
                </Button>
                
                {showApiPreview && apiValidation && (
                  <div className="space-y-4 p-4 border rounded bg-blue-50">
                    <h4 className="font-semibold">🔗 API Connection Results</h4>
                    
                    {apiValidation.success ? (
                      <>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-sm font-medium">Connection Status:</p>
                            <p className="text-sm text-green-600">✅ Successfully connected</p>
                            <p className="text-sm text-muted-foreground">{apiValidation.total} members found</p>
                          </div>
                          <div>
                            <p className="text-sm font-medium">Field Mapping:</p>
                            {apiValidation.mappingErrors.length === 0 ? (
                              <p className="text-sm text-green-600">✅ All required fields mapped correctly</p>
                            ) : (
                              <div className="text-sm text-red-600">
                                {apiValidation.mappingErrors.map((error, i) => (
                                  <p key={i}>❌ {error}</p>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                        
                        {apiValidation.qualityIssues.length > 0 && (
                          <div>
                            <p className="text-sm font-medium text-orange-600">⚠️ Data Quality Issues:</p>
                            <div className="text-xs text-orange-600 max-h-20 overflow-y-auto">
                              {apiValidation.qualityIssues.map((issue, i) => (
                                <p key={i}>• {issue}</p>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        <div className="max-h-48 overflow-auto border rounded bg-white p-2">
                          <p className="text-xs font-medium mb-2">Sample Data (first 5 rows):</p>
                          <table className="w-full text-xs">
                            <thead>
                              <tr>
                                {Object.entries(fieldMapping).map(([ourField, theirField]) => (
                                  <th key={ourField} className="border p-1 text-left">
                                    {ourField} ({theirField}) {apiValidation.mappingValid[ourField] ? '✅' : '❌'}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {apiPreview.slice(0, 5).map((row, i) => (
                                <tr key={i}>
                                  {Object.values(fieldMapping).map((theirField, j) => (
                                    <td key={j} className="border p-1">{row[theirField] || '-'}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        
                        {apiValidation.mappingErrors.length === 0 ? (
                          <Button onClick={handleApiSyncConfirm} className="bg-teal-500 hover:bg-teal-600 text-white">
                            ✅ Confirm API Sync Setup ({apiValidation.total} members, every {syncInterval} min)
                          </Button>
                        ) : (
                          <p className="text-red-600 text-sm">Fix field mapping errors before proceeding</p>
                        )}
                      </>
                    ) : (
                      <div className="text-red-600">
                        <p className="font-medium">❌ Connection Failed</p>
                        <p className="text-sm">{apiValidation.error}</p>
                        <p className="text-xs mt-2">Please check URL, API key, and network connection</p>
                      </div>
                    )}
                  </div>
                )}
                
                <Button type="submit" disabled={!apiUrl || importing || showApiPreview} className="bg-teal-500 hover:bg-teal-600 text-white">
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
        
        <TabsContent value="sync-status" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Active API Sync Jobs</CardTitle>
              <CardDescription>Monitor continuous synchronization status</CardDescription>
            </CardHeader>
            <CardContent>
              {activeSyncs.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No active sync jobs</p>
              ) : (
                <div className="space-y-3">
                  {activeSyncs.map(sync => (
                    <div key={sync.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${sync.status === 'active' ? 'bg-green-500' : 'bg-red-500'}`}></div>
                        <div>
                          <p className="font-semibold">{sync.name}</p>
                          <p className="text-sm text-muted-foreground">{sync.campus_name}</p>
                          <p className="text-xs text-muted-foreground">Every {sync.interval} minutes</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-green-600">✅ Synced</p>
                        <p className="text-xs text-muted-foreground">Last: {sync.last_sync.toLocaleTimeString()}</p>
                        <div className="flex gap-2 mt-2">
                          <Button size="sm" variant="outline" onClick={() => handleEditSync(sync.id)}>
                            Edit
                          </Button>
                          <Button size="sm" variant="outline">
                            Stop
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Edit Sync Dialog */}
          <Dialog open={editSyncOpen} onOpenChange={setEditSyncOpen}>
            <DialogContent className="max-w-3xl">
              <DialogHeader>
                <DialogTitle>Edit API Sync Job</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleUpdateSync} className="space-y-4">
                <div>
                  <Label>API URL</Label>
                  <Input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />
                </div>
                <div>
                  <Label>Sync Interval (minutes)</Label>
                  <Input type="number" value={syncInterval} onChange={(e) => setSyncInterval(parseInt(e.target.value))} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(fieldMapping).map(([key, value]) => (
                    <div key={key}>
                      <Label className="text-xs">{key.replace('_', ' ')}:</Label>
                      <Input 
                        value={value}
                        onChange={(e) => setFieldMapping({...fieldMapping, [key]: e.target.value})}
                        className="text-sm"
                      />
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 justify-end">
                  <Button type="button" variant="outline" onClick={() => setEditSyncOpen(false)}>Cancel</Button>
                  <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white">Update Sync</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ImportExport;
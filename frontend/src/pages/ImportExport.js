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
  const [csvFile, setCsvFile] = useState(null);
  const [jsonData, setJsonData] = useState('');
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [fieldMapping, setFieldMapping] = useState({
    name: 'name',
    phone: 'phone',
    email: 'email',
    external_id: 'id'
  });
  const [importing, setImporting] = useState(false);
  
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
                  <p className="text-xs text-muted-foreground mt-1">API endpoint that returns member data JSON</p>
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
                <div className="space-y-3">
                  <Label className="font-semibold">Field Mapping (map your API fields to our system)</Label>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="text-xs">Name field in your API:</Label>
                      <Input
                        value={fieldMapping.name}
                        onChange={(e) => setFieldMapping({...fieldMapping, name: e.target.value})}
                        placeholder="name"
                        className="text-sm"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Phone field:</Label>
                      <Input
                        value={fieldMapping.phone}
                        onChange={(e) => setFieldMapping({...fieldMapping, phone: e.target.value})}
                        placeholder="phone"
                        className="text-sm"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Email field (optional):</Label>
                      <Input
                        value={fieldMapping.email}
                        onChange={(e) => setFieldMapping({...fieldMapping, email: e.target.value})}
                        placeholder="email"
                        className="text-sm"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">ID field:</Label>
                      <Input
                        value={fieldMapping.external_id}
                        onChange={(e) => setFieldMapping({...fieldMapping, external_id: e.target.value})}
                        placeholder="id"
                        className="text-sm"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Example: If your API returns {`{full_name: "John", mobile: "628xxx"}`}, map name→full_name, phone→mobile
                  </p>
                </div>
                <Button type="submit" disabled={!apiUrl || importing} className="bg-teal-500 hover:bg-teal-600">
                  <FileJson className="w-4 h-4 mr-2" />
                  {importing ? 'Syncing...' : 'Sync from API'}
                </Button>
                <div className="p-3 bg-blue-50 rounded text-sm">
                  <p className="font-medium">💡 How it works:</p>
                  <p className="text-muted-foreground mt-1">System will fetch members from your external API and sync to this database. Existing members (matched by external_member_id) will be updated, new ones will be created.</p>
                </div>
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
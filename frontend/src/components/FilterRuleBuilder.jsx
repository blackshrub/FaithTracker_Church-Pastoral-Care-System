import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Plus, Trash2 } from 'lucide-react';

const FilterRuleBuilder = ({ availableFields, filterRules, onChange }) => {
  const addRule = () => {
    const newRule = {
      field: '',
      operator: 'equals',
      value: ''
    };
    onChange([...filterRules, newRule]);
  };

  const updateRule = (index, updates) => {
    const updated = [...filterRules];
    updated[index] = { ...updated[index], ...updates };
    onChange(updated);
  };

  const removeRule = (index) => {
    onChange(filterRules.filter((_, i) => i !== index));
  };

  const getOperatorsForType = (fieldType) => {
    switch (fieldType) {
      case 'string':
        return [
          { value: 'equals', label: 'Equals' },
          { value: 'not_equals', label: 'Not Equals' },
          { value: 'contains', label: 'Contains' },
          { value: 'in', label: 'In List' },
          { value: 'not_in', label: 'Not In List' }
        ];
      case 'number':
      case 'date':
        return [
          { value: 'equals', label: 'Equals' },
          { value: 'greater_than', label: 'Greater Than' },
          { value: 'less_than', label: 'Less Than' },
          { value: 'between', label: 'Between' }
        ];
      case 'boolean':
        return [
          { value: 'is_true', label: 'Is True' },
          { value: 'is_false', label: 'Is False' }
        ];
      default:
        return [{ value: 'equals', label: 'Equals' }];
    }
  };

  return (
    <div className="space-y-3">
      {filterRules.map((rule, index) => {
        const selectedField = availableFields.find(f => f.name === rule.field);
        const fieldType = selectedField?.type || 'string';
        const operators = getOperatorsForType(fieldType);
        const distinctValues = selectedField?.distinct_values || [];

        return (
          <div key={index} className="flex gap-2 items-start p-3 bg-gray-50 rounded-lg border">
            <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-2">
              {/* Field Selector */}
              <div>
                <Label className="text-xs">Field</Label>
                <Select value={rule.field} onValueChange={(v) => updateRule(index, { field: v, value: '' })}>
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select field" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableFields.map(field => (
                      <SelectItem key={field.name} value={field.name}>
                        {field.label} ({field.type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Operator Selector */}
              <div>
                <Label className="text-xs">Operator</Label>
                <Select value={rule.operator} onValueChange={(v) => updateRule(index, { operator: v })}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {operators.map(op => (
                      <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Value Input */}
              <div>
                <Label className="text-xs">Value</Label>
                {rule.operator === 'between' ? (
                  <div className="flex gap-1">
                    <Input 
                      type="number"
                      placeholder="Min"
                      value={Array.isArray(rule.value) ? rule.value[0] : ''}
                      onChange={(e) => updateRule(index, { value: [e.target.value, Array.isArray(rule.value) ? rule.value[1] : ''] })}
                      className="h-9"
                    />
                    <Input 
                      type="number"
                      placeholder="Max"
                      value={Array.isArray(rule.value) ? rule.value[1] : ''}
                      onChange={(e) => updateRule(index, { value: [Array.isArray(rule.value) ? rule.value[0] : '', e.target.value] })}
                      className="h-9"
                    />
                  </div>
                ) : rule.operator === 'is_true' || rule.operator === 'is_false' ? (
                  <Input value="(auto)" disabled className="h-9 bg-gray-100" />
                ) : distinctValues.length > 0 && distinctValues.length <= 10 ? (
                  <Select value={rule.value} onValueChange={(v) => updateRule(index, { value: v })}>
                    <SelectTrigger className="h-9">
                      <SelectValue placeholder="Select value" />
                    </SelectTrigger>
                    <SelectContent>
                      {distinctValues.map(val => (
                        <SelectItem key={val} value={val}>{val}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : rule.operator === 'in' || rule.operator === 'not_in' ? (
                  <Input 
                    placeholder="value1, value2, value3"
                    value={Array.isArray(rule.value) ? rule.value.join(', ') : rule.value}
                    onChange={(e) => {
                      const values = e.target.value.split(',').map(v => v.trim()).filter(v => v);
                      updateRule(index, { value: values });
                    }}
                    className="h-9"
                  />
                ) : (
                  <Input 
                    placeholder="Enter value"
                    value={rule.value}
                    onChange={(e) => updateRule(index, { value: e.target.value })}
                    className="h-9"
                  />
                )}
              </div>
            </div>

            {/* Remove Button */}
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => removeRule(index)}
              className="mt-5"
            >
              <Trash2 className="h-4 w-4 text-red-500" />
            </Button>
          </div>
        );
      })}

      <Button 
        onClick={addRule}
        variant="outline"
        size="sm"
        className="w-full gap-2"
        disabled={!availableFields || availableFields.length === 0}
      >
        <Plus className="h-4 w-4" />
        Add Filter Rule
      </Button>
      
      {(!availableFields || availableFields.length === 0) && (
        <p className="text-xs text-gray-500 text-center">
          Click "Discover Fields" to load available fields from core API
        </p>
      )}
    </div>
  );
};

export default FilterRuleBuilder;

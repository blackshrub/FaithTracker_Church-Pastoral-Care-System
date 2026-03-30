/// <reference types="vite/client" />

// Declare modules for unmigrated .jsx files (Shadcn/UI components, pages, etc.)
// These will be removed as files are migrated to TypeScript
declare module '*.jsx' {
  const component: React.ComponentType<any>;
  export default component;
  export const _: any;
}

// Shadcn/UI components (copy-pasted, not migrated)
declare module '@/components/ui/button' {
  export const Button: React.ComponentType<any>;
  export const buttonVariants: any;
}
declare module '@/components/ui/card' {
  export const Card: React.ComponentType<any>;
  export const CardContent: React.ComponentType<any>;
  export const CardHeader: React.ComponentType<any>;
  export const CardTitle: React.ComponentType<any>;
  export const CardDescription: React.ComponentType<any>;
}
declare module '@/components/ui/badge' {
  export const Badge: React.ComponentType<any>;
  export const badgeVariants: any;
}
declare module '@/components/ui/avatar' {
  export const Avatar: React.ComponentType<any>;
  export const AvatarImage: React.ComponentType<any>;
  export const AvatarFallback: React.ComponentType<any>;
}
declare module '@/components/ui/dialog' {
  export const Dialog: React.ComponentType<any>;
  export const DialogContent: React.ComponentType<any>;
  export const DialogHeader: React.ComponentType<any>;
  export const DialogTitle: React.ComponentType<any>;
  export const DialogDescription: React.ComponentType<any>;
  export const DialogTrigger: React.ComponentType<any>;
  export const DialogClose: React.ComponentType<any>;
}
declare module '@/components/ui/alert-dialog' {
  export const AlertDialog: React.ComponentType<any>;
  export const AlertDialogAction: React.ComponentType<any>;
  export const AlertDialogCancel: React.ComponentType<any>;
  export const AlertDialogContent: React.ComponentType<any>;
  export const AlertDialogDescription: React.ComponentType<any>;
  export const AlertDialogFooter: React.ComponentType<any>;
  export const AlertDialogHeader: React.ComponentType<any>;
  export const AlertDialogTitle: React.ComponentType<any>;
  export const AlertDialogTrigger: React.ComponentType<any>;
}
declare module '@/components/ui/input' {
  export const Input: React.ComponentType<any>;
}
declare module '@/components/ui/label' {
  export const Label: React.ComponentType<any>;
}
declare module '@/components/ui/select' {
  export const Select: React.ComponentType<any>;
  export const SelectContent: React.ComponentType<any>;
  export const SelectItem: React.ComponentType<any>;
  export const SelectTrigger: React.ComponentType<any>;
  export const SelectValue: React.ComponentType<any>;
}
declare module '@/components/ui/tabs' {
  export const Tabs: React.ComponentType<any>;
  export const TabsContent: React.ComponentType<any>;
  export const TabsList: React.ComponentType<any>;
  export const TabsTrigger: React.ComponentType<any>;
}
declare module '@/components/ui/popover' {
  export const Popover: React.ComponentType<any>;
  export const PopoverContent: React.ComponentType<any>;
  export const PopoverTrigger: React.ComponentType<any>;
}
declare module '@/components/ui/dropdown-menu' {
  export const DropdownMenu: React.ComponentType<any>;
  export const DropdownMenuContent: React.ComponentType<any>;
  export const DropdownMenuItem: React.ComponentType<any>;
  export const DropdownMenuTrigger: React.ComponentType<any>;
}
declare module '@/components/ui/separator' {
  export const Separator: React.ComponentType<any>;
}
declare module '@/components/ui/progress' {
  export const Progress: React.ComponentType<any>;
}
declare module '@/components/ui/skeleton' {
  export const Skeleton: React.ComponentType<any>;
}
declare module '@/components/ui/switch' {
  export const Switch: React.ComponentType<any>;
}
declare module '@/components/ui/textarea' {
  export const Textarea: React.ComponentType<any>;
}
declare module '@/components/ui/checkbox' {
  export const Checkbox: React.ComponentType<any>;
}
declare module '@/components/ui/sonner' {
  export const Toaster: React.ComponentType<any>;
}
declare module '@/components/ui/sheet' {
  export const Sheet: React.ComponentType<any>;
  export const SheetContent: React.ComponentType<any>;
  export const SheetHeader: React.ComponentType<any>;
  export const SheetTitle: React.ComponentType<any>;
  export const SheetTrigger: React.ComponentType<any>;
}
declare module '@/components/ui/form-field' {
  export const FormField: React.ComponentType<any>;
}
declare module '@/components/ui/calendar' {
  export const Calendar: React.ComponentType<any>;
}
declare module '@/components/ui/table' {
  export const Table: React.ComponentType<any>;
  export const TableBody: React.ComponentType<any>;
  export const TableCell: React.ComponentType<any>;
  export const TableHead: React.ComponentType<any>;
  export const TableHeader: React.ComponentType<any>;
  export const TableRow: React.ComponentType<any>;
}
declare module '@/components/ui/alert' {
  export const Alert: React.ComponentType<any>;
  export const AlertTitle: React.ComponentType<any>;
  export const AlertDescription: React.ComponentType<any>;
}

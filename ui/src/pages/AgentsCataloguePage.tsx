import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { Plus, Edit2, Trash2, Search, Filter, Store, ExternalLink, X, ChevronLeft, ChevronRight } from 'lucide-react'

import { apiClient } from '@/lib/api'
import { AgentsCatalogueItem, AgentsCatalogueConfig, AgentsCatalogueResponse } from '@/lib/api'
import { getFullUiUrl } from '@/lib/environment'

interface FilterState {
  search: string
  type: string
  tag: string
  owner: string
}

interface CreateFormData {
  name: string
  description: string
  type: string
  lifecycle: string
  owners: string
  tags: string[]
}

export function AgentsCataloguePage() {
  const [items, setItems] = useState<AgentsCatalogueItem[]>([])
  const [config, setConfig] = useState<AgentsCatalogueConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    type: '',
    tag: '',
    owner: ''
  })
  const [pagination, setPagination] = useState({
    page: 1,
    per_page: 20,
    total_pages: 1,
    total_items: 0,
    has_next: false,
    has_prev: false
  })

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingItem, setEditingItem] = useState<AgentsCatalogueItem | null>(null)
  const [createLoading, setCreateLoading] = useState(false)
  const [formData, setFormData] = useState<CreateFormData>({
    name: '',
    description: '',
    type: '',
    lifecycle: 'experimental',
    owners: '',
    tags: []
  })
  const [tagInput, setTagInput] = useState('')

  // Get unique tags and owners for filters
  const availableTags = [...new Set(items.flatMap(item => item.tags))].sort()
  const availableOwners = [...new Set(items.flatMap(item => item.owners))].sort()

      // Load agents catalogue config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const configData = await apiClient.getAgentsCatalogueConfig() as AgentsCatalogueConfig
        setConfig(configData)
        // Set default owner when config loads
        setFormData(prev => ({
          ...prev,
          owners: configData.default_owner || ''
        }))
      } catch (err) {
        console.error('Failed to load agents catalogue config:', err)
      }
    }
    loadConfig()
  }, [])

  // Load agents catalogue items
  const fetchItems = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        page: pagination.page,
        per_page: pagination.per_page,
        ...(filters.search && { search: filters.search }),
        ...(filters.type && { type: filters.type })
      };

      const response = await apiClient.getAgentsCatalogueItems(params) as AgentsCatalogueResponse;

      setItems(response.items);
      setPagination(response.pagination);
    } catch (error) {
      console.error("Failed to fetch agents catalogue items:", error);
      setError("Failed to fetch agents catalogue items. Please try again.");
      setItems([]);
      setPagination({
        page: 1,
        per_page: 20,
        total_pages: 1,
        total_items: 0,
        has_next: false,
        has_prev: false
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems()
  }, [filters, pagination.page])

  const handleFilterChange = (key: keyof FilterState, value: string) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }))
    setPagination(prev => ({ ...prev, page: 1 })) // Reset to first page
  }

  const getTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'api':
        return 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800'
      case 'microfrontend':
      case 'micro-frontend':
        return 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800'
      default:
        return 'bg-muted text-muted-foreground border-border'
    }
  }

  const getLifecycleColor = (lifecycle: string) => {
    switch (lifecycle.toLowerCase()) {
      case 'production':
        return 'bg-green-100 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800'
      case 'experimental':
        return 'bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800'
      case 'deprecated':
        return 'bg-red-100 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800'
      default:
        return 'bg-muted text-muted-foreground border-border'
    }
  }

  const handleItemClick = (item: AgentsCatalogueItem) => {
    // Check if item is in experimental or deprecated state
    const state = normalizeLifecycle(item.lifecycle)
    if (state === 'experimental' || state === 'deprecated') {
      // Don't allow navigation for experimental or deprecated items
      return
    }

    // Convert item name to URL format (kebab-case)
    const urlName = item.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

    // Use environment-specific UI base URL
    const uiBaseUrl = getFullUiUrl()
    const url = `${uiBaseUrl}/agents-catalogue/${item.type}/${urlName}`
    window.open(url, '_blank')
  }

  const normalizeLifecycle = (lifecycle: string) => lifecycle.toLowerCase()

  const isItemClickable = (item: AgentsCatalogueItem) => {
    const state = normalizeLifecycle(item.lifecycle)
    return state !== 'experimental' && state !== 'deprecated'
  }

  const getStatusMessage = (lifecycle: string) => {
    const state = normalizeLifecycle(lifecycle)
    switch (state) {
      case 'experimental':
        return 'This agent is experimental and not ready for production use'
      case 'deprecated':
        return 'This agent is deprecated and not ready for production use'
      default:
        return ''
    }
  }

  const resetForm = (defaultOwner?: string) => {
    setFormData({
      name: '',
      description: '',
      type: '',
      lifecycle: 'experimental',
      owners: defaultOwner || config?.default_owner || '',
      tags: []
    })
    setTagInput('')
  }

  const handleCreateItem = async () => {
    if (!formData.name.trim() || !formData.description.trim() || !formData.type.trim()) {
      alert('Please fill in all required fields')
      return
    }

    setCreateLoading(true)
    try {
      const itemData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        type: formData.type.trim(),
        lifecycle: formData.lifecycle,
        owners: formData.owners.split(',').map(owner => owner.trim()).filter(Boolean),
        tags: formData.tags
      }

      await apiClient.createAgentsCatalogueItem(itemData)

      setShowCreateModal(false)
      resetForm()
      fetchItems() // Refresh the list
    } catch (error) {
      console.error('Failed to create agents catalogue item:', error)
      alert('Failed to create agents catalogue item. Please try again.')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleEditItem = (item: AgentsCatalogueItem) => {
    setEditingItem(item)
    setFormData({
      name: item.name,
      description: item.description,
      type: item.type,
      lifecycle: item.lifecycle,
      owners: item.owners.join(', '),
      tags: item.tags
    })
    setShowEditModal(true)
  }

  const handleUpdateItem = async () => {
    if (!editingItem) return

    setCreateLoading(true)
    try {
      const itemData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        type: formData.type.trim(),
        lifecycle: formData.lifecycle,
        owners: formData.owners.split(',').map(owner => owner.trim()).filter(Boolean),
        tags: formData.tags
      }

      await apiClient.updateAgentsCatalogueItem(editingItem.id, itemData)

      setShowEditModal(false)
      setEditingItem(null)
      resetForm()
      fetchItems() // Refresh the list
    } catch (error) {
      console.error('Failed to update agents catalogue item:', error)
      alert('Failed to update agents catalogue item. Please try again.')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleDeleteItem = async (id: string) => {
    if (!confirm('Are you sure you want to delete this item?')) return

    try {
      await apiClient.deleteAgentsCatalogueItem(id)
      fetchItems() // Refresh the list
    } catch (error) {
      console.error('Failed to delete agents catalogue item:', error)
      alert('Failed to delete agents catalogue item. Please try again.')
    }
  }

  const addTag = () => {
    if (tagInput.trim() && !formData.tags.includes(tagInput.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...prev.tags, tagInput.trim()]
      }))
      setTagInput('')
    }
  }

  const removeTag = (tagToRemove: string) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags.filter(tag => tag !== tagToRemove)
    }))
  }

  const handlePageChange = (newPage: number) => {
    setPagination(prev => ({ ...prev, page: newPage }))
  }

  const clearFilters = () => {
    setFilters({
      search: '',
      type: '',
      tag: '',
      owner: ''
    })
    setPagination(prev => ({ ...prev, page: 1 }))
  }

  const filteredItems = items.filter(item => {
    const matchesTag = !filters.tag || item.tags.includes(filters.tag)
    const matchesOwner = !filters.owner || item.owners.includes(filters.owner)
    return matchesTag && matchesOwner
  })

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      {/* Background ambient effects */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />
      
      <div className="relative z-10 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6 mt-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
            <Store className="w-6 h-6 mr-2 text-emerald-500" />
            Agents Catalogue
          </h1>
          <p className="text-muted-foreground mt-1">Manage and discover automation agents</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Add Agent
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Store className="h-8 w-8 text-primary" />
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">Total Agents</p>
                <p className="text-2xl font-bold text-foreground">{pagination.total_items}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <div className="h-8 w-8 rounded-full bg-green-100 dark:bg-green-950 flex items-center justify-center">
                <div className="h-4 w-4 rounded-full bg-green-600 dark:bg-green-400"></div>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">Production</p>
                <p className="text-2xl font-bold text-foreground">
                  {items.filter(item => item.lifecycle === 'production').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <div className="h-8 w-8 rounded-full bg-purple-100 dark:bg-purple-950 flex items-center justify-center">
                <div className="h-4 w-4 rounded-full bg-purple-600 dark:bg-purple-400"></div>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">Micro Frontends</p>
                <p className="text-2xl font-bold text-foreground">
                  {items.filter(item => item.type === 'micro-frontend').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search agents..."
                  value={filters.search}
                  onChange={(e) => handleFilterChange('search', e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Type</label>
              <Select
                value={filters.type}
                onChange={(e) => handleFilterChange('type', e.target.value)}
              >
                <option value="">All Types</option>
                {config?.available_types.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Tag</label>
              <Select
                value={filters.tag}
                onChange={(e) => handleFilterChange('tag', e.target.value)}
              >
                <option value="">All Tags</option>
                {availableTags.map(tag => (
                  <option key={tag} value={tag}>
                    {tag}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Owner</label>
              <Select
                value={filters.owner}
                onChange={(e) => handleFilterChange('owner', e.target.value)}
              >
                <option value="">All Owners</option>
                {availableOwners.map(owner => (
                  <option key={owner} value={owner}>
                    {owner}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="mt-4 flex justify-between items-center">
            <div className="text-sm text-muted-foreground">
              Showing {filteredItems.length} of {pagination.total_items} agents
            </div>
            <Button variant="outline" onClick={clearFilters}>
              Clear Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Items List */}
      <Card>
        <CardHeader>
          <CardTitle>Agents</CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
              <p className="text-red-700 dark:text-red-300">{error}</p>
            </div>
          )}

          {items.length === 0 && !loading ? (
            <div className="text-center py-8">
              <Store className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No agents catalogue items found</p>
              <p className="text-sm text-muted-foreground">Try adjusting your search filters</p>
            </div>
          ) : (
            <>
              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-4 font-medium w-[30%] min-w-[250px]">Name</th>
                      <th className="text-left py-3 px-4 font-medium">Type</th>
                      <th className="text-left py-3 px-4 font-medium">Lifecycle</th>
                      <th className="text-left py-3 px-4 font-medium">Tags</th>
                      <th className="text-left py-3 px-4 font-medium">Owners</th>
                      <th className="text-left py-3 px-4 font-medium whitespace-nowrap">Updated</th>
                      <th className="text-left py-3 px-4 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={item.id} className={`border-b transition-colors ${
                        isItemClickable(item) 
                          ? 'hover:bg-muted/50' 
                          : 'opacity-75'
                      }`}>
                        <td className="py-3 px-4">
                          <div>
                            {isItemClickable(item) ? (
                              <button
                                onClick={() => handleItemClick(item)}
                                className="font-medium text-primary hover:text-primary/80 hover:underline text-left"
                              >
                                {item.name}
                                <ExternalLink className="h-3 w-3 ml-1 inline opacity-70" />
                              </button>
                            ) : (
                              <button 
                                disabled 
                                className="font-medium text-muted-foreground cursor-not-allowed text-left"
                                title={getStatusMessage(item.lifecycle)}
                              >
                                {item.name}
                              </button>
                            )}
                            <p className="text-sm text-muted-foreground">{item.description}</p>
                            {getStatusMessage(item.lifecycle) && (
                              <p className="text-xs text-orange-600 dark:text-orange-400 mt-1 italic">
                                {getStatusMessage(item.lifecycle)}
                              </p>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <Badge className={getTypeColor(item.type)}>
                            {item.type_display || item.type}
                          </Badge>
                        </td>
                        <td className="py-3 px-4">
                          <Badge className={getLifecycleColor(item.lifecycle)}>
                            {item.lifecycle}
                          </Badge>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-1">
                            {item.tags.map((tag, index) => (
                              <Badge key={index} variant="outline" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="text-sm text-muted-foreground">
                            {item.owners.join(', ')}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="text-sm text-muted-foreground">
                            {new Date(item.updated_at * 1000).toLocaleDateString()}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEditItem(item)}
                            >
                              <Edit2 className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteItem(item.id)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {pagination.total_pages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-gray-600">
                    Page {pagination.page} of {pagination.total_pages}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(pagination.page - 1)}
                      disabled={!pagination.has_prev}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(pagination.page + 1)}
                      disabled={!pagination.has_next}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Create Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Add New Agent</DialogTitle>
            <DialogClose onClick={() => setShowCreateModal(false)} />
          </DialogHeader>

          <div className="p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Name *</label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Agent name"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Type *</label>
                <Select
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                >
                  <option value="">Select type</option>
                  {config?.available_types.map(type => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Description *</label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Agent description"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Lifecycle</label>
                <Select
                  value={formData.lifecycle}
                  onChange={(e) => setFormData({ ...formData, lifecycle: e.target.value })}
                >
                  {config?.available_lifecycles.map(lifecycle => (
                    <option key={lifecycle} value={lifecycle}>
                      {lifecycle}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Owners</label>
                <Input
                  value={formData.owners}
                  onChange={(e) => setFormData({ ...formData, owners: e.target.value })}
                  placeholder="user@razorpay.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Tags</label>
              <div className="flex gap-2 mb-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  placeholder="Add tag"
                  onKeyPress={(e) => e.key === 'Enter' && addTag()}
                />
                <Button type="button" onClick={addTag} variant="outline">
                  Add
                </Button>
              </div>
              <div className="flex flex-wrap gap-1">
                {formData.tags.map((tag, index) => (
                  <Badge key={index} variant="secondary" className="flex items-center gap-1">
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-1 hover:bg-muted rounded-full p-1 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateItem} disabled={createLoading}>
              {createLoading ? 'Creating...' : 'Create Agent'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Agent</DialogTitle>
            <DialogClose onClick={() => setShowEditModal(false)} />
          </DialogHeader>

          <div className="p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Name *</label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Agent name"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Type *</label>
                <Select
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                >
                  <option value="">Select type</option>
                  {config?.available_types.map(type => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Description *</label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Agent description"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Lifecycle</label>
                <Select
                  value={formData.lifecycle}
                  onChange={(e) => setFormData({ ...formData, lifecycle: e.target.value })}
                >
                  {config?.available_lifecycles.map(lifecycle => (
                    <option key={lifecycle} value={lifecycle}>
                      {lifecycle}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Owners</label>
                <Input
                  value={formData.owners}
                  onChange={(e) => setFormData({ ...formData, owners: e.target.value })}
                  placeholder="user@razorpay.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Tags</label>
              <div className="flex gap-2 mb-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  placeholder="Add tag"
                  onKeyPress={(e) => e.key === 'Enter' && addTag()}
                />
                <Button type="button" onClick={addTag} variant="outline">
                  Add
                </Button>
              </div>
              <div className="flex flex-wrap gap-1">
                {formData.tags.map((tag, index) => (
                  <Badge key={index} variant="secondary" className="flex items-center gap-1">
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-1 hover:bg-muted rounded-full p-1 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateItem} disabled={createLoading}>
              {createLoading ? 'Updating...' : 'Update Agent'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
    </div>
  )
}

export default AgentsCataloguePage
import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  Heading,
  VStack,
  HStack,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  useToast,
  Input,
  Select,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  Switch,
  Text,
  Alert,
  AlertIcon,
  Spinner,
  useColorModeValue,
  Tag,
  Tooltip,
} from '@chakra-ui/react'
import { FiPlus, FiEdit, FiTrash2, FiEye, FiEyeOff } from 'react-icons/fi'
import {
  adminApi,
  type AdminSetting,
  type AdminSettingCreate,
  type AdminSettingUpdate,
  type ConfigStatusResponse,
} from '../../api/admin'

const CATEGORIES = [
  { value: '', label: 'All Categories' },
  { value: 'email', label: 'Email' },
  { value: 'ai', label: 'AI / OpenAI' },
  { value: 'processing', label: 'Processing' },
  { value: 'application', label: 'Application' },
  { value: 'system', label: 'System' },
]

const VALUE_TYPES = ['string', 'number', 'boolean', 'json'] as const

export const AdminConfigPage = () => {
  const [settings, setSettings] = useState<AdminSetting[]>([])
  const [configStatus, setConfigStatus] = useState<ConfigStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [statusLoading, setStatusLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingSetting, setEditingSetting] = useState<AdminSetting | null>(null)
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})

  const [formData, setFormData] = useState<AdminSettingCreate>({
    key: '',
    value: '',
    value_type: 'string',
    is_secret: false,
    description: '',
    category: 'system',
  })

  const toast = useToast()
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const bgColor = useColorModeValue('white', 'gray.800')

  useEffect(() => {
    loadSettings()
    loadConfigStatus()
  }, [category, search])

  const loadSettings = async () => {
    try {
      setLoading(true)
      const response = await adminApi.listSettings({
        category: category || undefined,
        search: search || undefined,
        page: 1,
        page_size: 100,
      })
      setSettings(response.items)
    } catch (error) {
      toast({
        title: 'Error loading settings',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setLoading(false)
    }
  }

  const loadConfigStatus = async () => {
    try {
      setStatusLoading(true)
      const status = await adminApi.getConfigStatus()
      setConfigStatus(status)
    } catch (error) {
      console.error('Failed to load config status:', error)
    } finally {
      setStatusLoading(false)
    }
  }

  const openCreateModal = () => {
    setEditingSetting(null)
    setFormData({
      key: '',
      value: '',
      value_type: 'string',
      is_secret: false,
      description: '',
      category: 'system',
    })
    setIsModalOpen(true)
  }

  const openEditModal = (setting: AdminSetting) => {
    setEditingSetting(setting)
    setFormData({
      key: setting.key,
      value: setting.value,
      value_type: setting.value_type,
      is_secret: setting.is_secret,
      description: setting.description,
      category: setting.category,
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      if (editingSetting) {
        // Update existing setting
        const updateData: AdminSettingUpdate = {
          value: formData.value,
          value_type: formData.value_type,
          is_secret: formData.is_secret,
          description: formData.description,
          category: formData.category,
        }
        await adminApi.updateSetting(editingSetting.key, updateData)
        toast({
          title: 'Setting updated',
          status: 'success',
          duration: 3000,
        })
      } else {
        // Create new setting
        await adminApi.createSetting(formData)
        toast({
          title: 'Setting created',
          status: 'success',
          duration: 3000,
        })
      }

      setIsModalOpen(false)
      loadSettings()
      loadConfigStatus()
    } catch (error) {
      toast({
        title: editingSetting ? 'Error updating setting' : 'Error creating setting',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  const handleDelete = async (key: string) => {
    if (!confirm(`Are you sure you want to delete setting "${key}"?`)) {
      return
    }

    try {
      await adminApi.deleteSetting(key)
      toast({
        title: 'Setting deleted',
        status: 'success',
        duration: 3000,
      })
      loadSettings()
      loadConfigStatus()
    } catch (error) {
      toast({
        title: 'Error deleting setting',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  const toggleSecretVisibility = (key: string) => {
    setShowSecrets((prev) => ({
      ...prev,
      [key]: !prev[key],
    }))
  }

  const renderValue = (setting: AdminSetting) => {
    if (setting.is_secret && !showSecrets[setting.key]) {
      return '••••••••'
    }

    switch (setting.value_type) {
      case 'boolean':
        return <Badge colorScheme={setting.value ? 'green' : 'red'}>{String(setting.value)}</Badge>
      case 'json':
        return <Text fontSize="sm" fontFamily="mono">{JSON.stringify(setting.value)}</Text>
      default:
        return <Text>{String(setting.value)}</Text>
    }
  }

  return (
    <Box>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <HStack justify="space-between">
          <Heading size="lg">System Configuration</Heading>
          <Button leftIcon={<FiPlus />} colorScheme="blue" onClick={openCreateModal}>
            Add Setting
          </Button>
        </HStack>

        {/* Configuration Status Alert */}
        {!statusLoading && configStatus && (
          <>
            {configStatus.is_healthy ? (
              <Alert status="success">
                <AlertIcon />
                <Box>
                  <Text fontWeight="bold">
                    All configuration settings are properly configured ✓
                  </Text>
                  <Text fontSize="sm">
                    {configStatus.valid_count} of {configStatus.total_expected} expected settings are valid
                  </Text>
                </Box>
              </Alert>
            ) : (
              <Alert status="warning">
                <AlertIcon />
                <Box flex="1">
                  <Text fontWeight="bold">
                    Configuration Issues Detected
                  </Text>
                  <Text fontSize="sm">
                    {configStatus.missing_count > 0 && `${configStatus.missing_count} missing, `}
                    {configStatus.incomplete_count > 0 && `${configStatus.incomplete_count} incomplete`}
                  </Text>
                  {configStatus.recommendations.length > 0 && (
                    <VStack align="stretch" mt={2} spacing={1}>
                      {configStatus.recommendations.map((rec, idx) => (
                        <Text key={idx} fontSize="sm" fontFamily="mono">
                          • {rec}
                        </Text>
                      ))}
                    </VStack>
                  )}
                </Box>
              </Alert>
            )}

            {/* Missing Settings */}
            {configStatus.missing.length > 0 && (
              <Box borderWidth="1px" borderRadius="lg" borderColor="red.300" p={4} bg={useColorModeValue('red.50', 'red.900')}>
                <Heading size="sm" color="red.600" mb={3}>
                  ❌ Missing Required Settings ({configStatus.missing.length})
                </Heading>
                <VStack align="stretch" spacing={2}>
                  {configStatus.missing.map((issue) => (
                    <Box key={issue.key} p={2} bg={bgColor} borderRadius="md">
                      <HStack justify="space-between">
                        <VStack align="start" spacing={0}>
                          <Text fontWeight="bold">{issue.key}</Text>
                          <Text fontSize="sm" color="gray.600">{issue.description}</Text>
                          <Badge colorScheme="purple">{issue.category}</Badge>
                        </VStack>
                        {issue.required && <Tag colorScheme="red" size="sm">Required</Tag>}
                      </HStack>
                    </Box>
                  ))}
                </VStack>
              </Box>
            )}

            {/* Incomplete Settings */}
            {configStatus.incomplete.length > 0 && (
              <Box borderWidth="1px" borderRadius="lg" borderColor="orange.300" p={4} bg={useColorModeValue('orange.50', 'orange.900')}>
                <Heading size="sm" color="orange.600" mb={3}>
                  ⚠️ Incomplete Settings ({configStatus.incomplete.length})
                </Heading>
                <VStack align="stretch" spacing={2}>
                  {configStatus.incomplete.map((issue) => (
                    <Box key={issue.key} p={2} bg={bgColor} borderRadius="md">
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="bold">{issue.key}</Text>
                        <Text fontSize="sm" color="gray.600">
                          Issues: {issue.issues?.join(', ')}
                        </Text>
                        <Badge colorScheme="purple">{issue.category}</Badge>
                      </VStack>
                    </Box>
                  ))}
                </VStack>
              </Box>
            )}
          </>
        )}

        <Alert status="info">
          <AlertIcon />
          Manage system-wide configuration settings including API keys, email configuration, and AI processing.
        </Alert>

        {/* Filters */}
        <HStack spacing={4}>
          <Select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            maxW="250px"
            bg={bgColor}
          >
            {CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </Select>

          <Input
            placeholder="Search by key or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            maxW="400px"
            bg={bgColor}
          />
        </HStack>

        {/* Settings Table */}
        {loading ? (
          <Box textAlign="center" py={10}>
            <Spinner size="xl" />
          </Box>
        ) : settings.length === 0 ? (
          <Box textAlign="center" py={10}>
            <Text color="gray.500">No settings found</Text>
          </Box>
        ) : (
          <Box borderWidth="1px" borderRadius="lg" borderColor={borderColor} overflow="hidden">
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Key</Th>
                  <Th>Value</Th>
                  <Th>Type</Th>
                  <Th>Category</Th>
                  <Th>Description</Th>
                  <Th width="150px">Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {settings.map((setting) => (
                  <Tr key={setting.id}>
                    <Td fontWeight="medium">
                      <HStack>
                        <Text>{setting.key}</Text>
                        {setting.is_secret && <Tag size="sm" colorScheme="red">Secret</Tag>}
                      </HStack>
                    </Td>
                    <Td maxW="300px" overflow="hidden" textOverflow="ellipsis">
                      {renderValue(setting)}
                    </Td>
                    <Td>
                      <Badge>{setting.value_type}</Badge>
                    </Td>
                    <Td>
                      <Badge colorScheme="purple">{setting.category || 'none'}</Badge>
                    </Td>
                    <Td maxW="200px" overflow="hidden" textOverflow="ellipsis">
                      <Text fontSize="sm" color="gray.600">{setting.description || '-'}</Text>
                    </Td>
                    <Td>
                      <HStack spacing={2}>
                        {setting.is_secret && (
                          <Tooltip label={showSecrets[setting.key] ? 'Hide value' : 'Show value'}>
                            <IconButton
                              aria-label="Toggle visibility"
                              icon={showSecrets[setting.key] ? <FiEyeOff /> : <FiEye />}
                              size="sm"
                              variant="ghost"
                              onClick={() => toggleSecretVisibility(setting.key)}
                            />
                          </Tooltip>
                        )}
                        <IconButton
                          aria-label="Edit"
                          icon={<FiEdit />}
                          size="sm"
                          colorScheme="blue"
                          variant="ghost"
                          onClick={() => openEditModal(setting)}
                        />
                        <IconButton
                          aria-label="Delete"
                          icon={<FiTrash2 />}
                          size="sm"
                          colorScheme="red"
                          variant="ghost"
                          onClick={() => handleDelete(setting.key)}
                        />
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        )}
      </VStack>

      {/* Create/Edit Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{editingSetting ? 'Edit Setting' : 'Create Setting'}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Key</FormLabel>
                <Input
                  value={formData.key}
                  onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                  placeholder="setting_key"
                  isDisabled={!!editingSetting}
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Value</FormLabel>
                {formData.value_type === 'boolean' ? (
                  <Select
                    value={String(formData.value)}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value === 'true' })}
                  >
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </Select>
                ) : formData.value_type === 'json' ? (
                  <Textarea
                    value={typeof formData.value === 'string' ? formData.value : JSON.stringify(formData.value, null, 2)}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                    placeholder='{"key": "value"}'
                    fontFamily="mono"
                    rows={5}
                  />
                ) : (
                  <Input
                    value={String(formData.value)}
                    onChange={(e) => setFormData({ ...formData, value: formData.value_type === 'number' ? Number(e.target.value) : e.target.value })}
                    type={formData.value_type === 'number' ? 'number' : 'text'}
                    placeholder="value"
                  />
                )}
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Value Type</FormLabel>
                <Select
                  value={formData.value_type}
                  onChange={(e) => setFormData({ ...formData, value_type: e.target.value as any })}
                >
                  {VALUE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Category</FormLabel>
                <Select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                >
                  {CATEGORIES.filter((c) => c.value).map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe what this setting does"
                  rows={3}
                />
              </FormControl>

              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">Is Secret?</FormLabel>
                <Switch
                  isChecked={formData.is_secret}
                  onChange={(e) => setFormData({ ...formData, is_secret: e.target.checked })}
                />
                <Text ml={3} fontSize="sm" color="gray.600">
                  (Values will be encrypted)
                </Text>
              </FormControl>
            </VStack>
          </ModalBody>

          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={handleSubmit}>
              {editingSetting ? 'Update' : 'Create'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  )
}

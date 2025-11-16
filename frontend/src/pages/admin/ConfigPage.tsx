import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  HStack,
  VStack,
  Input,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  useDisclosure,
  useToast,
  Heading,
  Text,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  FormControl,
  FormLabel,
  FormHelperText,
  Switch,
  Textarea,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
} from '@chakra-ui/react'
import { FiEdit, FiTrash2, FiPlus, FiEye, FiEyeOff } from 'react-icons/fi'
import { adminApi, AdminSetting, AdminSettingCreate, AdminSettingUpdate } from '../../api/admin'

export const ConfigPage = () => {
  const [settings, setSettings] = useState<AdminSetting[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [selectedSetting, setSelectedSetting] = useState<AdminSetting | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [showSecretValues, setShowSecretValues] = useState<Record<string, boolean>>({})

  const { isOpen, onOpen, onClose } = useDisclosure()
  const toast = useToast()

  // Form state
  const [formData, setFormData] = useState<AdminSettingCreate>({
    key: '',
    value: '',
    value_type: 'string',
    is_secret: false,
    description: '',
    category: 'api_keys',
  })

  useEffect(() => {
    loadSettings()
  }, [search, categoryFilter])

  const loadSettings = async () => {
    setIsLoading(true)
    try {
      const response = await adminApi.listSettings({
        search: search || undefined,
        category: categoryFilter || undefined,
        page: 1,
        page_size: 100,
      })
      setSettings(response.items)
    } catch (error: any) {
      toast({
        title: 'Failed to load settings',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 3000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreate = () => {
    setIsCreating(true)
    setSelectedSetting(null)
    setFormData({
      key: '',
      value: '',
      value_type: 'string',
      is_secret: false,
      description: '',
      category: 'api_keys',
    })
    onOpen()
  }

  const handleEdit = async (setting: AdminSetting) => {
    setIsCreating(false)
    setSelectedSetting(setting)

    // Fetch the setting with decrypted value if it's a secret
    try {
      const fullSetting = await adminApi.getSetting(setting.key, true)
      setFormData({
        key: fullSetting.key,
        value: fullSetting.value,
        value_type: fullSetting.value_type,
        is_secret: fullSetting.is_secret,
        description: fullSetting.description || '',
        category: fullSetting.category || 'api_keys',
      })
      onOpen()
    } catch (error: any) {
      toast({
        title: 'Failed to load setting',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 3000,
      })
    }
  }

  const handleSave = async () => {
    try {
      if (isCreating) {
        await adminApi.createSetting(formData)
        toast({
          title: 'Setting created',
          status: 'success',
          duration: 2000,
        })
      } else if (selectedSetting) {
        const updateData: AdminSettingUpdate = {
          value: formData.value,
          value_type: formData.value_type,
          is_secret: formData.is_secret,
          description: formData.description,
          category: formData.category,
        }
        await adminApi.updateSetting(selectedSetting.key, updateData)
        toast({
          title: 'Setting updated',
          status: 'success',
          duration: 2000,
        })
      }
      onClose()
      loadSettings()
    } catch (error: any) {
      toast({
        title: isCreating ? 'Failed to create setting' : 'Failed to update setting',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 3000,
      })
    }
  }

  const handleDelete = async (key: string) => {
    if (!window.confirm('Are you sure you want to delete this setting?')) {
      return
    }

    try {
      await adminApi.deleteSetting(key)
      toast({
        title: 'Setting deleted',
        status: 'success',
        duration: 2000,
      })
      loadSettings()
    } catch (error: any) {
      toast({
        title: 'Failed to delete setting',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 3000,
      })
    }
  }

  const toggleShowSecret = (key: string) => {
    setShowSecretValues(prev => ({
      ...prev,
      [key]: !prev[key],
    }))
  }

  const formatValue = (setting: AdminSetting) => {
    if (setting.is_secret && !showSecretValues[setting.key]) {
      return '••••••••'
    }
    if (typeof setting.value === 'object') {
      return JSON.stringify(setting.value)
    }
    return String(setting.value)
  }

  const parseFormValue = (value: string, valueType: string): any => {
    switch (valueType) {
      case 'number':
        return parseFloat(value)
      case 'boolean':
        return value === 'true'
      case 'json':
        try {
          return JSON.parse(value)
        } catch {
          return value
        }
      default:
        return value
    }
  }

  return (
    <VStack spacing={6} align="stretch">
      <Box>
        <Heading size="lg" mb={2}>Configuration Settings</Heading>
        <Text color="gray.600">Manage application configuration, API keys, and system settings</Text>
      </Box>

      <Alert status="warning">
        <AlertIcon />
        <Box>
          <AlertTitle>Sensitive Information</AlertTitle>
          <AlertDescription>
            Secret values are encrypted in the database. Be careful when viewing or editing them.
          </AlertDescription>
        </Box>
      </Alert>

      {/* Filters */}
      <HStack spacing={4}>
        <Input
          placeholder="Search settings..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          maxW="400px"
        />
        <Select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          maxW="200px"
        >
          <option value="">All Categories</option>
          <option value="api_keys">API Keys</option>
          <option value="openai">OpenAI</option>
          <option value="email">Email</option>
          <option value="features">Features</option>
          <option value="system">System</option>
        </Select>
        <Button leftIcon={<FiPlus />} colorScheme="blue" onClick={handleCreate} ml="auto">
          Add Setting
        </Button>
      </HStack>

      {/* Settings Table */}
      {isLoading ? (
        <Box textAlign="center" py={10}>
          <Spinner size="xl" />
        </Box>
      ) : settings.length === 0 ? (
        <Box textAlign="center" py={10}>
          <Text color="gray.500">No settings found</Text>
        </Box>
      ) : (
        <Box overflowX="auto" borderWidth="1px" borderRadius="md">
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Key</Th>
                <Th>Category</Th>
                <Th>Type</Th>
                <Th>Value</Th>
                <Th>Description</Th>
                <Th>Updated</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {settings.map((setting) => (
                <Tr key={setting.id}>
                  <Td fontFamily="mono" fontSize="sm">{setting.key}</Td>
                  <Td>
                    <Badge colorScheme="purple">{setting.category || 'system'}</Badge>
                  </Td>
                  <Td>
                    <Badge colorScheme="gray">{setting.value_type}</Badge>
                    {setting.is_secret && <Badge colorScheme="red" ml={2}>Secret</Badge>}
                  </Td>
                  <Td fontFamily="mono" fontSize="sm" maxW="300px" isTruncated>
                    {formatValue(setting)}
                    {setting.is_secret && (
                      <IconButton
                        icon={showSecretValues[setting.key] ? <FiEyeOff /> : <FiEye />}
                        aria-label="Toggle visibility"
                        size="xs"
                        ml={2}
                        onClick={() => toggleShowSecret(setting.key)}
                      />
                    )}
                  </Td>
                  <Td maxW="200px" isTruncated>{setting.description || '-'}</Td>
                  <Td fontSize="sm" color="gray.600">
                    {new Date(setting.updated_at).toLocaleDateString()}
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <IconButton
                        icon={<FiEdit />}
                        aria-label="Edit"
                        size="sm"
                        onClick={() => handleEdit(setting)}
                      />
                      <IconButton
                        icon={<FiTrash2 />}
                        aria-label="Delete"
                        size="sm"
                        colorScheme="red"
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

      {/* Create/Edit Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{isCreating ? 'Create Setting' : 'Edit Setting'}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Key</FormLabel>
                <Input
                  value={formData.key}
                  onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                  isDisabled={!isCreating}
                  placeholder="e.g., sendgrid.api_key"
                />
                <FormHelperText>Unique identifier for this setting</FormHelperText>
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Category</FormLabel>
                <Select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                >
                  <option value="api_keys">API Keys</option>
                  <option value="openai">OpenAI</option>
                  <option value="email">Email</option>
                  <option value="features">Features</option>
                  <option value="system">System</option>
                </Select>
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Value Type</FormLabel>
                <Select
                  value={formData.value_type}
                  onChange={(e) => setFormData({ ...formData, value_type: e.target.value as any })}
                >
                  <option value="string">String</option>
                  <option value="number">Number</option>
                  <option value="boolean">Boolean</option>
                  <option value="json">JSON</option>
                </Select>
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Value</FormLabel>
                {formData.value_type === 'json' ? (
                  <Textarea
                    value={typeof formData.value === 'object' ? JSON.stringify(formData.value, null, 2) : formData.value}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                    fontFamily="mono"
                    rows={6}
                  />
                ) : formData.value_type === 'boolean' ? (
                  <Select
                    value={String(formData.value)}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </Select>
                ) : (
                  <Input
                    value={String(formData.value)}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                    type={formData.value_type === 'number' ? 'number' : 'text'}
                  />
                )}
              </FormControl>

              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="What this setting controls..."
                />
              </FormControl>

              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">Is Secret</FormLabel>
                <Switch
                  isChecked={formData.is_secret}
                  onChange={(e) => setFormData({ ...formData, is_secret: e.target.checked })}
                />
                <FormHelperText ml={4}>Will be encrypted in the database</FormHelperText>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={() => {
                // Parse the value based on type before saving
                const parsedFormData = {
                  ...formData,
                  value: parseFormValue(String(formData.value), formData.value_type),
                }
                setFormData(parsedFormData)
                handleSave()
              }}
            >
              {isCreating ? 'Create' : 'Update'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </VStack>
  )
}

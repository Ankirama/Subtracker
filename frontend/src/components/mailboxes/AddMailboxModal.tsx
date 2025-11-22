import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  useToast,
  Alert,
  AlertIcon,
  AlertDescription,
  InputGroup,
  InputRightElement,
  IconButton,
  Icon,
  HStack,
  Text,
  Divider,
} from '@chakra-ui/react'
import { FiEye, FiEyeOff, FiCheckCircle, FiXCircle } from 'react-icons/fi'
import { mailboxesAPI } from '../../api/mailboxes'
import { Mailbox, MailboxCreate, MailboxUpdate } from '../../types'

interface AddMailboxModalProps {
  isOpen: boolean
  onClose: () => void
  mailbox: Mailbox | null
}

export const AddMailboxModal = ({
  isOpen,
  onClose,
  mailbox,
}: AddMailboxModalProps) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    server_url: '',
    username: '',
    password: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [connectionTested, setConnectionTested] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  const queryClient = useQueryClient()
  const toast = useToast()

  useEffect(() => {
    if (mailbox) {
      setFormData({
        name: mailbox.display_name || '',
        email: mailbox.email_address,
        server_url: '', // Server URL is not returned for security
        username: mailbox.email_address, // Use email as username default
        password: '', // Don't pre-fill password for security
      })
      setConnectionTested(true) // Assume existing mailbox is valid
    } else {
      // Reset form for new mailbox
      setFormData({
        name: '',
        email: '',
        server_url: '',
        username: '',
        password: '',
      })
      setConnectionTested(false)
      setTestResult(null)
    }
  }, [mailbox, isOpen])

  const testConnectionMutation = useMutation({
    mutationFn: () =>
      mailboxesAPI.testConnection({
        server_url: formData.server_url,
        username: formData.username,
        password: formData.password,
      }),
    onSuccess: (data) => {
      setConnectionTested(true)
      setTestResult({
        success: data.success,
        message: data.message || 'Connection successful!',
      })
      toast({
        title: 'Connection test successful',
        description: 'JMAP server credentials are valid',
        status: 'success',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      setConnectionTested(false)
      setTestResult({
        success: false,
        message: error.response?.data?.detail || 'Connection test failed',
      })
      toast({
        title: 'Connection test failed',
        description: error.response?.data?.detail || 'Failed to connect to JMAP server',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const createMutation = useMutation({
    mutationFn: mailboxesAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mailboxes'] })
      toast({
        title: 'Mailbox added',
        description: 'Email sync will start automatically',
        status: 'success',
        duration: 3000,
      })
      onClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to add mailbox',
        description: error.response?.data?.detail || 'Please try again',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: MailboxUpdate }) =>
      mailboxesAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mailboxes'] })
      toast({
        title: 'Mailbox updated',
        status: 'success',
        duration: 3000,
      })
      onClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to update mailbox',
        description: error.response?.data?.detail || 'Please try again',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const handleTestConnection = () => {
    if (!formData.server_url || !formData.username || !formData.password) {
      toast({
        title: 'Missing credentials',
        description: 'Please fill in all JMAP connection fields',
        status: 'warning',
        duration: 3000,
      })
      return
    }
    testConnectionMutation.mutate()
  }

  const handleSubmit = () => {
    // Validation
    if (!formData.name || !formData.email || !formData.server_url || !formData.username) {
      toast({
        title: 'Missing fields',
        description: 'Please fill in all required fields',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    // For new mailboxes, require connection test
    if (!mailbox && !connectionTested) {
      toast({
        title: 'Test connection first',
        description: 'Please test the connection before saving',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    if (mailbox) {
      // Update existing mailbox
      const updateData: MailboxUpdate = {
        display_name: formData.name || null,
      }

      // Include credentials only if any field changed
      if (formData.server_url && formData.username && formData.password) {
        updateData.credentials = {
          server_url: formData.server_url,
          username: formData.username,
          password: formData.password,
        }
      }

      updateMutation.mutate({ id: mailbox.id, data: updateData })
    } else {
      // Create new mailbox
      const createData: MailboxCreate = {
        provider_type: 'jmap',
        email_address: formData.email,
        display_name: formData.name || null,
        credentials: {
          server_url: formData.server_url,
          username: formData.username,
          password: formData.password,
        },
      }

      createMutation.mutate(createData)
    }
  }

  const handleClose = () => {
    setConnectionTested(false)
    setTestResult(null)
    onClose()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      size={{ base: 'full', md: 'lg' }}
      motionPreset="slideInBottom"
    >
      <ModalOverlay />
      <ModalContent
        maxH={{ base: '100vh', md: 'auto' }}
        my={{ base: 0, md: 'auto' }}
      >
        <ModalHeader>
          {mailbox ? 'Edit Mailbox' : 'Add Mailbox'}
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody overflowY="auto" px={{ base: 4, md: 6 }} py={{ base: 4, md: 6 }}>
          <VStack spacing={4}>
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <AlertDescription fontSize="sm">
                Connect your email using JMAP protocol. We'll scan for subscription-related emails.
              </AlertDescription>
            </Alert>

            <FormControl isRequired>
              <FormLabel>Mailbox Name</FormLabel>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Personal Email, Work Account"
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Email Address</FormLabel>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="your.email@example.com"
              />
            </FormControl>

            <Divider />

            <Text fontSize="sm" fontWeight="bold" alignSelf="flex-start" color="gray.700">
              JMAP Server Configuration
            </Text>

            <FormControl isRequired>
              <FormLabel>JMAP Server URL</FormLabel>
              <Input
                value={formData.server_url}
                onChange={(e) => {
                  setFormData({ ...formData, server_url: e.target.value })
                  setConnectionTested(false)
                  setTestResult(null)
                }}
                placeholder="https://jmap.fastmail.com"
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Username</FormLabel>
              <Input
                value={formData.username}
                onChange={(e) => {
                  setFormData({ ...formData, username: e.target.value })
                  setConnectionTested(false)
                  setTestResult(null)
                }}
                placeholder="your.email@example.com"
              />
            </FormControl>

            <FormControl isRequired={!mailbox}>
              <FormLabel>
                Password / App-Specific Password
                {mailbox && (
                  <Text as="span" fontSize="xs" color="gray.500" ml={2}>
                    (leave empty to keep current)
                  </Text>
                )}
              </FormLabel>
              <InputGroup>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={(e) => {
                    setFormData({ ...formData, password: e.target.value })
                    setConnectionTested(false)
                    setTestResult(null)
                  }}
                  placeholder="••••••••"
                />
                <InputRightElement>
                  <IconButton
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    icon={<Icon as={showPassword ? FiEyeOff : FiEye} />}
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowPassword(!showPassword)}
                  />
                </InputRightElement>
              </InputGroup>
            </FormControl>

            {/* Test Connection Button */}
            <HStack w="full" spacing={2}>
              <Button
                onClick={handleTestConnection}
                isLoading={testConnectionMutation.isPending}
                variant="outline"
                colorScheme="blue"
                size="sm"
                flex={1}
              >
                Test Connection
              </Button>
              {testResult && (
                <HStack spacing={1}>
                  <Icon
                    as={testResult.success ? FiCheckCircle : FiXCircle}
                    color={testResult.success ? 'green.500' : 'red.500'}
                  />
                  <Text fontSize="sm" color={testResult.success ? 'green.600' : 'red.600'}>
                    {testResult.success ? 'Connected' : 'Failed'}
                  </Text>
                </HStack>
              )}
            </HStack>

            {testResult && !testResult.success && (
              <Alert status="error" borderRadius="md">
                <AlertIcon />
                <AlertDescription fontSize="sm">{testResult.message}</AlertDescription>
              </Alert>
            )}
          </VStack>
        </ModalBody>

        <ModalFooter
          px={{ base: 4, md: 6 }}
          py={{ base: 4, md: 6 }}
          borderTopWidth={{ base: '1px', md: 0 }}
          position={{ base: 'sticky', md: 'relative' }}
          bottom={{ base: 0, md: 'auto' }}
          bg="white"
        >
          <Button variant="ghost" mr={3} onClick={handleClose} w={{ base: 'full', md: 'auto' }}>
            Cancel
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSubmit}
            isLoading={createMutation.isPending || updateMutation.isPending}
            isDisabled={!mailbox && !connectionTested}
            w={{ base: 'full', md: 'auto' }}
          >
            {mailbox ? 'Save Changes' : 'Add Mailbox'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

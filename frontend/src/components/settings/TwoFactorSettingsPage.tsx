import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  Container,
  VStack,
  Heading,
  Text,
  useToast,
  Alert,
  AlertIcon,
  Badge,
  Divider,
  FormControl,
  FormLabel,
  Input,
  RadioGroup,
  Radio,
  Stack,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Image,
  Code,
  useDisclosure,
  HStack,
  IconButton,
  Textarea,
} from '@chakra-ui/react'
import { CopyIcon, RepeatIcon, LockIcon, UnlockIcon } from '@chakra-ui/icons'
import { authAPI } from '../../api/auth'
import { TwoFactorStatusResponse } from '../../types'

export const TwoFactorSettingsPage = () => {
  const [status, setStatus] = useState<TwoFactorStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const toast = useToast()

  // Fetch 2FA status
  useEffect(() => {
    fetchStatus()
  }, [])

  const fetchStatus = async () => {
    try {
      const statusData = await authAPI.get2FAStatus()
      setStatus(statusData)
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to fetch 2FA status'
      setError(message)
      toast({
        title: 'Error',
        description: message,
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Container maxW="4xl" py={8}>
      <VStack spacing={8} align="stretch">
        <Box>
          <Heading size="lg" mb={2}>
            🔐 Two-Factor Authentication
          </Heading>
          <Text color="text.subtle">
            Add an extra layer of security to your account
          </Text>
        </Box>

        {error && !isLoading && (
          <Alert status="error" borderRadius="md">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {!isLoading && status && (
          <>
            {/* Current Status */}
            <Box p={6} borderWidth={1} borderRadius="lg" bg="white" boxShadow="sm">
              <HStack justifyContent="space-between" mb={4}>
                <Heading size="md">Current Status</Heading>
                <Badge
                  colorScheme={status.enabled ? 'green' : 'gray'}
                  fontSize="md"
                  px={3}
                  py={1}
                  borderRadius="full"
                >
                  {status.enabled ? 'Enabled' : 'Disabled'}
                </Badge>
              </HStack>

              {status.enabled && (
                <VStack align="start" spacing={2}>
                  <HStack>
                    <Text fontWeight="bold">Method:</Text>
                    <Badge colorScheme="blue">
                      {status.method === 'totp' ? 'Authenticator App' : 'Email OTP'}
                    </Badge>
                  </HStack>
                  <HStack>
                    <Text fontWeight="bold">Backup Codes Remaining:</Text>
                    <Badge colorScheme={status.backup_codes_remaining > 3 ? 'green' : 'orange'}>
                      {status.backup_codes_remaining} / 10
                    </Badge>
                  </HStack>
                  {status.backup_codes_remaining < 3 && (
                    <Alert status="warning" borderRadius="md" mt={2}>
                      <AlertIcon />
                      <Text fontSize="sm">
                        You're running low on backup codes. Consider regenerating them.
                      </Text>
                    </Alert>
                  )}
                </VStack>
              )}

              {!status.enabled && (
                <Text color="text.subtle">
                  Two-factor authentication is not enabled. Enable it below to add extra security to your account.
                </Text>
              )}
            </Box>

            <Divider />

            {/* Enable or Disable 2FA */}
            {!status.enabled ? (
              <EnableTwoFactorSection onSuccess={fetchStatus} />
            ) : (
              <>
                <DisableTwoFactorSection onSuccess={fetchStatus} />
                <BackupCodesSection backupCodesRemaining={status.backup_codes_remaining} />
              </>
            )}
          </>
        )}

        {isLoading && (
          <Box textAlign="center" py={8}>
            <Text color="text.subtle">Loading 2FA settings...</Text>
          </Box>
        )}
      </VStack>
    </Container>
  )
}

// Enable 2FA Section Component
const EnableTwoFactorSection = ({ onSuccess }: { onSuccess: () => void }) => {
  const [method, setMethod] = useState<'totp' | 'email'>('totp')
  const [isSettingUp, setIsSettingUp] = useState(false)
  const [setupData, setSetupData] = useState<any>(null)
  const { isOpen, onOpen, onClose } = useDisclosure()
  const toast = useToast()

  const handleSetup = async () => {
    setIsSettingUp(true)
    try {
      const response = await authAPI.setup2FA({ method })
      setSetupData(response)
      onOpen()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to setup 2FA'
      toast({
        title: 'Setup Failed',
        description: message,
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsSettingUp(false)
    }
  }

  const handleCloseModal = () => {
    onClose()
    setSetupData(null)
  }

  return (
    <Box p={6} borderWidth={1} borderRadius="lg" bg="white" boxShadow="sm">
      <Heading size="md" mb={4}>
        <HStack>
          <LockIcon color="green.500" />
          <Text>Enable Two-Factor Authentication</Text>
        </HStack>
      </Heading>

      <VStack align="start" spacing={4}>
        <FormControl>
          <FormLabel>Choose 2FA Method</FormLabel>
          <RadioGroup value={method} onChange={(value: 'totp' | 'email') => setMethod(value)}>
            <Stack spacing={4}>
              <Radio value="totp">
                <Box>
                  <Text fontWeight="bold">Authenticator App (TOTP)</Text>
                  <Text fontSize="sm" color="text.subtle">
                    Use apps like Google Authenticator, Authy, or 1Password
                  </Text>
                </Box>
              </Radio>
              <Radio value="email">
                <Box>
                  <Text fontWeight="bold">Email OTP</Text>
                  <Text fontSize="sm" color="text.subtle">
                    Receive verification codes via email
                  </Text>
                </Box>
              </Radio>
            </Stack>
          </RadioGroup>
        </FormControl>

        <Button
          colorScheme="green"
          leftIcon={<LockIcon />}
          onClick={handleSetup}
          isLoading={isSettingUp}
          loadingText="Setting up..."
        >
          Setup {method === 'totp' ? 'Authenticator App' : 'Email OTP'}
        </Button>
      </VStack>

      {/* Setup Modal */}
      {setupData && (
        <SetupModal
          isOpen={isOpen}
          onClose={handleCloseModal}
          setupData={setupData}
          onSuccess={() => {
            handleCloseModal()
            onSuccess()
          }}
        />
      )}
    </Box>
  )
}

// Setup Modal Component
const SetupModal = ({
  isOpen,
  onClose,
  setupData,
  onSuccess,
}: {
  isOpen: boolean
  onClose: () => void
  setupData: any
  onSuccess: () => void
}) => {
  const [verificationCode, setVerificationCode] = useState('')
  const [isEnabling, setIsEnabling] = useState(false)
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [showBackupCodes, setShowBackupCodes] = useState(false)
  const toast = useToast()

  const handleEnable = async () => {
    setIsEnabling(true)
    try {
      const response = await authAPI.enable2FA({
        method: setupData.method,
        secret: setupData.secret,
        verification_code: verificationCode,
      })

      setBackupCodes(response.backup_codes)
      setShowBackupCodes(true)

      toast({
        title: 'Success!',
        description: '2FA has been enabled successfully',
        status: 'success',
        duration: 5000,
      })
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to enable 2FA'
      toast({
        title: 'Verification Failed',
        description: message,
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsEnabling(false)
    }
  }

  const handleCopyBackupCodes = () => {
    const codesText = backupCodes.join('\n')
    navigator.clipboard.writeText(codesText)
    toast({
      title: 'Copied!',
      description: 'Backup codes copied to clipboard',
      status: 'success',
      duration: 2000,
    })
  }

  const handleFinish = () => {
    onSuccess()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg" closeOnOverlayClick={false}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          {showBackupCodes ? 'Save Your Backup Codes' : `Setup ${setupData.method === 'totp' ? 'Authenticator App' : 'Email OTP'}`}
        </ModalHeader>
        <ModalCloseButton isDisabled={isEnabling} />
        <ModalBody>
          {!showBackupCodes ? (
            <VStack spacing={4} align="stretch">
              {setupData.method === 'totp' && setupData.qr_code && (
                <>
                  <Text>Scan this QR code with your authenticator app:</Text>
                  <Box textAlign="center">
                    <Image src={setupData.qr_code} alt="QR Code" maxW="250px" mx="auto" />
                  </Box>
                  <Text fontSize="sm" color="text.subtle">
                    Or enter this secret key manually:
                  </Text>
                  <Code p={2} borderRadius="md" fontSize="sm">
                    {setupData.secret}
                  </Code>
                </>
              )}

              {setupData.method === 'email' && (
                <Alert status="info" borderRadius="md">
                  <AlertIcon />
                  <Text fontSize="sm">{setupData.message}</Text>
                </Alert>
              )}

              <FormControl isRequired>
                <FormLabel>Enter Verification Code</FormLabel>
                <Input
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  placeholder="123456"
                  maxLength={6}
                  autoFocus
                />
                <Text fontSize="xs" color="text.subtle" mt={1}>
                  Enter the 6-digit code from your {setupData.method === 'totp' ? 'authenticator app' : 'email'}
                </Text>
              </FormControl>
            </VStack>
          ) : (
            <VStack spacing={4} align="stretch">
              <Alert status="warning" borderRadius="md">
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontWeight="bold">Important: Save these backup codes!</Text>
                  <Text fontSize="sm">
                    These codes can be used to access your account if you lose access to your 2FA method.
                    Each code can only be used once.
                  </Text>
                </VStack>
              </Alert>

              <Box>
                <HStack justifyContent="space-between" mb={2}>
                  <Text fontWeight="bold">Your Backup Codes:</Text>
                  <IconButton
                    aria-label="Copy codes"
                    icon={<CopyIcon />}
                    size="sm"
                    onClick={handleCopyBackupCodes}
                  />
                </HStack>
                <Textarea
                  value={backupCodes.join('\n')}
                  readOnly
                  fontFamily="monospace"
                  rows={10}
                  resize="none"
                />
              </Box>

              <Alert status="info" borderRadius="md">
                <AlertIcon />
                <Text fontSize="sm">
                  Store these codes in a safe place. You won't be able to see them again!
                </Text>
              </Alert>
            </VStack>
          )}
        </ModalBody>
        <ModalFooter>
          {!showBackupCodes ? (
            <>
              <Button variant="ghost" onClick={onClose} mr={3} isDisabled={isEnabling}>
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={handleEnable}
                isLoading={isEnabling}
                loadingText="Enabling..."
                isDisabled={verificationCode.length !== 6}
              >
                Enable 2FA
              </Button>
            </>
          ) : (
            <Button colorScheme="green" onClick={handleFinish}>
              I've Saved My Backup Codes
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

// Disable 2FA Section Component
const DisableTwoFactorSection = ({ onSuccess }: { onSuccess: () => void }) => {
  const [password, setPassword] = useState('')
  const [isDisabling, setIsDisabling] = useState(false)
  const { isOpen, onOpen, onClose } = useDisclosure()
  const toast = useToast()

  const handleDisable = async () => {
    setIsDisabling(true)
    try {
      await authAPI.disable2FA({ password })
      toast({
        title: 'Success',
        description: '2FA has been disabled',
        status: 'success',
        duration: 3000,
      })
      onClose()
      setPassword('')
      onSuccess()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to disable 2FA'
      toast({
        title: 'Failed',
        description: message,
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsDisabling(false)
    }
  }

  return (
    <>
      <Box p={6} borderWidth={1} borderRadius="lg" bg="white" boxShadow="sm">
        <Heading size="md" mb={4}>
          <HStack>
            <UnlockIcon color="red.500" />
            <Text>Disable Two-Factor Authentication</Text>
          </HStack>
        </Heading>

        <VStack align="start" spacing={4}>
          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            <Text fontSize="sm">
              Disabling 2FA will make your account less secure. You'll need to enter your password to confirm.
            </Text>
          </Alert>

          <Button
            colorScheme="red"
            variant="outline"
            leftIcon={<UnlockIcon />}
            onClick={onOpen}
          >
            Disable 2FA
          </Button>
        </VStack>
      </Box>

      {/* Disable Confirmation Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Confirm Disable 2FA</ModalHeader>
          <ModalCloseButton isDisabled={isDisabling} />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Alert status="warning" borderRadius="md">
                <AlertIcon />
                <Text fontSize="sm">
                  Are you sure you want to disable two-factor authentication? This will make your account less secure.
                </Text>
              </Alert>

              <FormControl isRequired>
                <FormLabel>Enter Your Password</FormLabel>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoFocus
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="ghost"
              onClick={() => {
                onClose()
                setPassword('')
              }}
              mr={3}
              isDisabled={isDisabling}
            >
              Cancel
            </Button>
            <Button
              colorScheme="red"
              onClick={handleDisable}
              isLoading={isDisabling}
              loadingText="Disabling..."
              isDisabled={!password}
            >
              Disable 2FA
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  )
}

// Backup Codes Section Component
const BackupCodesSection = ({ backupCodesRemaining }: { backupCodesRemaining: number }) => {
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [newBackupCodes, setNewBackupCodes] = useState<string[]>([])
  const { isOpen, onOpen, onClose } = useDisclosure()
  const toast = useToast()

  const handleRegenerate = async () => {
    setIsRegenerating(true)
    try {
      const response = await authAPI.regenerateBackupCodes()
      setNewBackupCodes(response.backup_codes)
      onOpen()
      toast({
        title: 'Success',
        description: 'Backup codes regenerated successfully',
        status: 'success',
        duration: 3000,
      })
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to regenerate backup codes'
      toast({
        title: 'Failed',
        description: message,
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsRegenerating(false)
    }
  }

  const handleCopyBackupCodes = () => {
    const codesText = newBackupCodes.join('\n')
    navigator.clipboard.writeText(codesText)
    toast({
      title: 'Copied!',
      description: 'Backup codes copied to clipboard',
      status: 'success',
      duration: 2000,
    })
  }

  return (
    <>
      <Box p={6} borderWidth={1} borderRadius="lg" bg="white" boxShadow="sm">
        <Heading size="md" mb={4}>
          Backup Codes
        </Heading>

        <VStack align="start" spacing={4}>
          <Text color="text.subtle">
            Backup codes allow you to access your account if you lose your 2FA device. Each code can only be used once.
          </Text>

          <HStack>
            <Text fontWeight="bold">Codes Remaining:</Text>
            <Badge colorScheme={backupCodesRemaining > 3 ? 'green' : 'orange'} fontSize="md">
              {backupCodesRemaining} / 10
            </Badge>
          </HStack>

          <Button
            colorScheme="blue"
            leftIcon={<RepeatIcon />}
            onClick={handleRegenerate}
            isLoading={isRegenerating}
            loadingText="Regenerating..."
          >
            Regenerate Backup Codes
          </Button>

          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            <Text fontSize="sm">
              Regenerating will invalidate all existing backup codes and create 10 new ones.
            </Text>
          </Alert>
        </VStack>
      </Box>

      {/* New Backup Codes Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Your New Backup Codes</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Alert status="warning" borderRadius="md">
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontWeight="bold">Save these codes now!</Text>
                  <Text fontSize="sm">
                    All previous backup codes have been invalidated. Store these new codes in a safe place.
                  </Text>
                </VStack>
              </Alert>

              <Box>
                <HStack justifyContent="space-between" mb={2}>
                  <Text fontWeight="bold">Your New Backup Codes:</Text>
                  <IconButton
                    aria-label="Copy codes"
                    icon={<CopyIcon />}
                    size="sm"
                    onClick={handleCopyBackupCodes}
                  />
                </HStack>
                <Textarea
                  value={newBackupCodes.join('\n')}
                  readOnly
                  fontFamily="monospace"
                  rows={10}
                  resize="none"
                />
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="green" onClick={onClose}>
              I've Saved My Backup Codes
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  )
}

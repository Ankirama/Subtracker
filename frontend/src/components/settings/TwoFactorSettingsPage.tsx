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
import { useTranslation } from 'react-i18next'
import { CopyIcon, RepeatIcon, LockIcon, UnlockIcon } from '@chakra-ui/icons'
import { authAPI } from '../../api/auth'
import { TwoFactorStatusResponse } from '../../types'

export const TwoFactorSettingsPage = () => {
  const { t } = useTranslation()
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
            🔐 {t('settings:twoFactor.title')}
          </Heading>
          <Text color="text.subtle">
            {t('settings:twoFactor.subtitle')}
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
                <Heading size="md">{t('settings:twoFactor.currentStatus')}</Heading>
                <Badge
                  colorScheme={status.enabled ? 'green' : 'gray'}
                  fontSize="md"
                  px={3}
                  py={1}
                  borderRadius="full"
                >
                  {status.enabled ? t('settings:twoFactor.enabled') : t('settings:twoFactor.disabled')}
                </Badge>
              </HStack>

              {status.enabled && (
                <VStack align="start" spacing={2}>
                  <HStack>
                    <Text fontWeight="bold">{t('settings:twoFactor.method')}:</Text>
                    <Badge colorScheme="blue">
                      {status.method === 'totp' ? t('settings:twoFactor.authenticatorApp') : t('settings:twoFactor.emailOTP')}
                    </Badge>
                  </HStack>
                  <HStack>
                    <Text fontWeight="bold">{t('settings:twoFactor.backupCodesRemaining')}:</Text>
                    <Badge colorScheme={status.backup_codes_remaining > 3 ? 'green' : 'orange'}>
                      {status.backup_codes_remaining} / 10
                    </Badge>
                  </HStack>
                  {status.backup_codes_remaining < 3 && (
                    <Alert status="warning" borderRadius="md" mt={2}>
                      <AlertIcon />
                      <Text fontSize="sm">
                        {t('settings:twoFactor.lowBackupCodesWarning')}
                      </Text>
                    </Alert>
                  )}
                </VStack>
              )}

              {!status.enabled && (
                <Text color="text.subtle">
                  {t('settings:twoFactor.notEnabledMessage')}
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
            <Text color="text.subtle">{t('settings:twoFactor.loading')}</Text>
          </Box>
        )}
      </VStack>
    </Container>
  )
}

// Enable 2FA Section Component
const EnableTwoFactorSection = ({ onSuccess }: { onSuccess: () => void }) => {
  const { t } = useTranslation()
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
        title: t('settings:twoFactor.enable.setupFailed'),
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
          <Text>{t('settings:twoFactor.enable.title')}</Text>
        </HStack>
      </Heading>

      <VStack align="start" spacing={4}>
        <FormControl>
          <FormLabel>{t('settings:twoFactor.enable.chooseMethod')}</FormLabel>
          <RadioGroup value={method} onChange={(value: 'totp' | 'email') => setMethod(value)}>
            <Stack spacing={4}>
              <Radio value="totp">
                <Box>
                  <Text fontWeight="bold">{t('settings:twoFactor.enable.totpOption')}</Text>
                  <Text fontSize="sm" color="text.subtle">
                    {t('settings:twoFactor.enable.totpDescription')}
                  </Text>
                </Box>
              </Radio>
              <Radio value="email">
                <Box>
                  <Text fontWeight="bold">{t('settings:twoFactor.enable.emailOption')}</Text>
                  <Text fontSize="sm" color="text.subtle">
                    {t('settings:twoFactor.enable.emailDescription')}
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
          loadingText={t('settings:twoFactor.enable.settingUp')}
        >
          {t('settings:twoFactor.enable.setupButton', { method: method === 'totp' ? t('settings:twoFactor.authenticatorApp') : t('settings:twoFactor.emailOTP') })}
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
  const { t } = useTranslation()
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
        description: t('settings:twoFactor.enable.success'),
        status: 'success',
        duration: 5000,
      })
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to enable 2FA'
      toast({
        title: t('settings:twoFactor.enable.verificationFailed'),
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
      title: t('settings:twoFactor.backupCodes.copied'),
      description: t('settings:twoFactor.backupCodes.copiedDescription'),
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
          {showBackupCodes ? t('settings:twoFactor.backupCodes.saveTitle') : `${t('settings:twoFactor.enable.setupButton', { method: setupData.method === 'totp' ? t('settings:twoFactor.authenticatorApp') : t('settings:twoFactor.emailOTP') })}`}
        </ModalHeader>
        <ModalCloseButton isDisabled={isEnabling} />
        <ModalBody>
          {!showBackupCodes ? (
            <VStack spacing={4} align="stretch">
              {setupData.method === 'totp' && setupData.qr_code && (
                <>
                  <Text>{t('settings:twoFactor.enable.scanQR')}</Text>
                  <Box textAlign="center">
                    <Image src={setupData.qr_code} alt="QR Code" maxW="250px" mx="auto" />
                  </Box>
                  <Text fontSize="sm" color="text.subtle">
                    {t('settings:twoFactor.enable.manualEntry')}
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
                <FormLabel>{t('settings:twoFactor.enable.enterCode')}</FormLabel>
                <Input
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  placeholder="123456"
                  maxLength={6}
                  autoFocus
                />
                <Text fontSize="xs" color="text.subtle" mt={1}>
                  {t('settings:twoFactor.enable.codeHelp', { source: setupData.method === 'totp' ? t('settings:twoFactor.enable.authenticatorSource') : t('settings:twoFactor.enable.emailSource') })}
                </Text>
              </FormControl>
            </VStack>
          ) : (
            <VStack spacing={4} align="stretch">
              <Alert status="warning" borderRadius="md">
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontWeight="bold">{t('settings:twoFactor.backupCodes.saveWarning')}</Text>
                  <Text fontSize="sm">
                    {t('settings:twoFactor.backupCodes.saveDescription')}
                  </Text>
                </VStack>
              </Alert>

              <Box>
                <HStack justifyContent="space-between" mb={2}>
                  <Text fontWeight="bold">{t('settings:twoFactor.backupCodes.yourCodes')}</Text>
                  <IconButton
                    aria-label={t('settings:twoFactor.backupCodes.copyAriaLabel')}
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
                  {t('settings:twoFactor.backupCodes.saveInstruction')}
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
                loadingText={t('settings:twoFactor.enable.enabling')}
                isDisabled={verificationCode.length !== 6}
              >
                {t('settings:twoFactor.enable.enableButton')}
              </Button>
            </>
          ) : (
            <Button colorScheme="green" onClick={handleFinish}>
              {t('settings:twoFactor.backupCodes.confirmSaved')}
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

// Disable 2FA Section Component
const DisableTwoFactorSection = ({ onSuccess }: { onSuccess: () => void }) => {
  const { t } = useTranslation()
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
        description: t('settings:twoFactor.disable.success'),
        status: 'success',
        duration: 3000,
      })
      onClose()
      setPassword('')
      onSuccess()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to disable 2FA'
      toast({
        title: t('settings:twoFactor.disable.failed'),
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
            <Text>{t('settings:twoFactor.disable.title')}</Text>
          </HStack>
        </Heading>

        <VStack align="start" spacing={4}>
          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            <Text fontSize="sm">
              {t('settings:twoFactor.disable.warning')}
            </Text>
          </Alert>

          <Button
            colorScheme="red"
            variant="outline"
            leftIcon={<UnlockIcon />}
            onClick={onOpen}
          >
            {t('settings:twoFactor.disable.button')}
          </Button>
        </VStack>
      </Box>

      {/* Disable Confirmation Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('settings:twoFactor.disable.confirmTitle')}</ModalHeader>
          <ModalCloseButton isDisabled={isDisabling} />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Alert status="warning" borderRadius="md">
                <AlertIcon />
                <Text fontSize="sm">
                  {t('settings:twoFactor.disable.confirmWarning')}
                </Text>
              </Alert>

              <FormControl isRequired>
                <FormLabel>{t('settings:twoFactor.disable.enterPassword')}</FormLabel>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t('settings:twoFactor.disable.passwordPlaceholder')}
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
              loadingText={t('settings:twoFactor.disable.disabling')}
              isDisabled={!password}
            >
              {t('settings:twoFactor.disable.button')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  )
}

// Backup Codes Section Component
const BackupCodesSection = ({ backupCodesRemaining }: { backupCodesRemaining: number }) => {
  const { t } = useTranslation()
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
        description: t('settings:twoFactor.backupCodes.regenerateSuccess'),
        status: 'success',
        duration: 3000,
      })
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to regenerate backup codes'
      toast({
        title: 'Failed',
        description: t('settings:twoFactor.backupCodes.regenerateFailed'),
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
      title: t('settings:twoFactor.backupCodes.copied'),
      description: t('settings:twoFactor.backupCodes.copiedDescription'),
      status: 'success',
      duration: 2000,
    })
  }

  return (
    <>
      <Box p={6} borderWidth={1} borderRadius="lg" bg="white" boxShadow="sm">
        <Heading size="md" mb={4}>
          {t('settings:twoFactor.backupCodes.title')}
        </Heading>

        <VStack align="start" spacing={4}>
          <Text color="text.subtle">
            {t('settings:twoFactor.backupCodes.description')}
          </Text>

          <HStack>
            <Text fontWeight="bold">{t('settings:twoFactor.backupCodes.codesRemaining')}:</Text>
            <Badge colorScheme={backupCodesRemaining > 3 ? 'green' : 'orange'} fontSize="md">
              {backupCodesRemaining} / 10
            </Badge>
          </HStack>

          <Button
            colorScheme="blue"
            leftIcon={<RepeatIcon />}
            onClick={handleRegenerate}
            isLoading={isRegenerating}
            loadingText={t('settings:twoFactor.backupCodes.regenerating')}
          >
            {t('settings:twoFactor.backupCodes.regenerateButton')}
          </Button>

          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            <Text fontSize="sm">
              {t('settings:twoFactor.backupCodes.regenerateWarning')}
            </Text>
          </Alert>
        </VStack>
      </Box>

      {/* New Backup Codes Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('settings:twoFactor.backupCodes.newCodesTitle')}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Alert status="warning" borderRadius="md">
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontWeight="bold">{t('settings:twoFactor.backupCodes.newCodesWarning')}</Text>
                  <Text fontSize="sm">
                    {t('settings:twoFactor.backupCodes.newCodesDescription')}
                  </Text>
                </VStack>
              </Alert>

              <Box>
                <HStack justifyContent="space-between" mb={2}>
                  <Text fontWeight="bold">{t('settings:twoFactor.backupCodes.yourCodes')}</Text>
                  <IconButton
                    aria-label={t('settings:twoFactor.backupCodes.copyAriaLabel')}
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
              {t('settings:twoFactor.backupCodes.confirmSaved')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  )
}

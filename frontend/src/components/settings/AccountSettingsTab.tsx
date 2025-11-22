import { useState } from 'react'
import {
  Box,
  VStack,
  Heading,
  FormControl,
  FormLabel,
  Input,
  Button,
  useToast,
  Card,
  CardBody,
  CardHeader,
  Text,
  Alert,
  AlertIcon,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
} from '@chakra-ui/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../contexts/AuthContext'
import { authAPI } from '../../api/auth'
import type { ProfileUpdateRequest, DeleteAccountRequest } from '../../types'
import { useRef } from 'react'
import { useNavigate } from 'react-router-dom'

export function AccountSettingsTab() {
  const { user } = useAuth()
  const toast = useToast()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { isOpen, onOpen, onClose } = useDisclosure()
  const cancelRef = useRef<HTMLButtonElement>(null)

  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [deletePassword, setDeletePassword] = useState('')

  const updateProfileMutation = useMutation({
    mutationFn: (data: ProfileUpdateRequest) => authAPI.updateProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentUser'] })
      toast({
        title: 'Profile updated',
        description: 'Your profile has been successfully updated.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Update failed',
        description: error.response?.data?.detail || 'Failed to update profile',
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    },
  })

  const deleteAccountMutation = useMutation({
    mutationFn: (data: DeleteAccountRequest) => authAPI.deleteAccount(data),
    onSuccess: () => {
      toast({
        title: 'Account deleted',
        description: 'Your account has been permanently deleted.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      })
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      navigate('/login')
    },
    onError: (error: any) => {
      toast({
        title: 'Deletion failed',
        description: error.response?.data?.detail || 'Failed to delete account',
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    },
  })

  const handleUpdateProfile = () => {
    const data: ProfileUpdateRequest = {}

    if (displayName !== user?.display_name) {
      data.display_name = displayName || null
    }

    if (email !== user?.email) {
      data.email = email
    }

    if (Object.keys(data).length > 0) {
      updateProfileMutation.mutate(data)
    } else {
      toast({
        title: 'No changes',
        description: 'No changes detected to update.',
        status: 'info',
        duration: 3000,
        isClosable: true,
      })
    }
  }

  const handleDeleteAccount = () => {
    if (!deletePassword) {
      toast({
        title: 'Password required',
        description: 'Please enter your password to confirm account deletion.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      })
      return
    }

    deleteAccountMutation.mutate({
      password: deletePassword,
      confirm: true,
    })
  }

  return (
    <VStack spacing={6} align="stretch">
      <Card>
        <CardHeader>
          <Heading size="md">Profile Information</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel>Display Name</FormLabel>
              <Input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Enter your display name"
              />
            </FormControl>

            <FormControl>
              <FormLabel>Email Address</FormLabel>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
              />
              <Text fontSize="sm" color="gray.500" mt={1}>
                Changing your email will require re-verification
              </Text>
            </FormControl>

            <Button
              colorScheme="blue"
              onClick={handleUpdateProfile}
              isLoading={updateProfileMutation.isPending}
              size={{ base: 'md', md: 'md' }}
              width={{ base: 'full', md: 'auto' }}
            >
              Update Profile
            </Button>
          </VStack>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <Heading size="md" color="red.500">
            Danger Zone
          </Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <Alert status="warning">
              <AlertIcon />
              Deleting your account is permanent and cannot be undone. All your data will be lost.
            </Alert>

            <Box>
              <Button colorScheme="red" onClick={onOpen}>
                Delete Account
              </Button>
            </Box>
          </VStack>
        </CardBody>
      </Card>

      <AlertDialog
        isOpen={isOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete Account
            </AlertDialogHeader>

            <AlertDialogBody>
              <VStack spacing={4} align="stretch">
                <Text>
                  Are you absolutely sure? This action cannot be undone. All your subscriptions,
                  mailboxes, and data will be permanently deleted.
                </Text>
                <FormControl>
                  <FormLabel>Enter your password to confirm</FormLabel>
                  <Input
                    type="password"
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    placeholder="Password"
                  />
                </FormControl>
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClose}>
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={() => {
                  handleDeleteAccount()
                  onClose()
                }}
                ml={3}
                isLoading={deleteAccountMutation.isPending}
              >
                Delete Account
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  )
}

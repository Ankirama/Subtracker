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
  Divider,
} from '@chakra-ui/react'
import { useMutation } from '@tanstack/react-query'
import { authAPI } from '../../api/auth'
import type { PasswordChangeRequest } from '../../types'
import { TwoFactorSettingsPage } from './TwoFactorSettingsPage'

export function SecuritySettingsTab() {
  const toast = useToast()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const changePasswordMutation = useMutation({
    mutationFn: (data: PasswordChangeRequest) => authAPI.changePassword(data),
    onSuccess: () => {
      toast({
        title: 'Password changed',
        description: 'Your password has been successfully updated.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    },
    onError: (error: any) => {
      toast({
        title: 'Password change failed',
        description: error.response?.data?.detail || 'Failed to change password',
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    },
  })

  const handleChangePassword = () => {
    // Validation
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast({
        title: 'Missing fields',
        description: 'Please fill in all password fields.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      })
      return
    }

    if (newPassword !== confirmPassword) {
      toast({
        title: 'Passwords do not match',
        description: 'New password and confirmation do not match.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      })
      return
    }

    if (newPassword.length < 8) {
      toast({
        title: 'Password too short',
        description: 'Password must be at least 8 characters long.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      })
      return
    }

    changePasswordMutation.mutate({
      current_password: currentPassword,
      new_password: newPassword,
    })
  }

  return (
    <VStack spacing={6} align="stretch">
      <Card>
        <CardHeader>
          <Heading size="md">Change Password</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel>Current Password</FormLabel>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
              />
            </FormControl>

            <FormControl>
              <FormLabel>New Password</FormLabel>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password (min 8 characters)"
              />
              <Text fontSize="sm" color="gray.500" mt={1}>
                Must be at least 8 characters with letters and numbers
              </Text>
            </FormControl>

            <FormControl>
              <FormLabel>Confirm New Password</FormLabel>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
              />
            </FormControl>

            <Button
              colorScheme="blue"
              onClick={handleChangePassword}
              isLoading={changePasswordMutation.isPending}
              size={{ base: 'md', md: 'md' }}
              width={{ base: 'full', md: 'auto' }}
            >
              Change Password
            </Button>
          </VStack>
        </CardBody>
      </Card>

      <Divider />

      <Box>
        <TwoFactorSettingsPage />
      </Box>
    </VStack>
  )
}

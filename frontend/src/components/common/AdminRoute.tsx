import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { Box, Spinner, Text, VStack } from '@chakra-ui/react'

interface AdminRouteProps {
  children: React.ReactNode
}

export const AdminRoute: React.FC<AdminRouteProps> = ({ children }) => {
  const { user, isLoading, isAuthenticated } = useAuth()

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minH="100vh">
        <VStack spacing={4}>
          <Spinner size="xl" color="blue.500" />
          <Text>Loading...</Text>
        </VStack>
      </Box>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />
  }

  // Redirect to dashboard if not an admin
  if (!user.is_admin) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minH="100vh">
        <VStack spacing={4}>
          <Text fontSize="2xl" fontWeight="bold">Access Denied</Text>
          <Text color="gray.600">You need admin privileges to access this page.</Text>
          <Text color="blue.500" cursor="pointer" onClick={() => window.location.href = '/dashboard'}>
            Return to Dashboard
          </Text>
        </VStack>
      </Box>
    )
  }

  // User is authenticated and is an admin
  return <>{children}</>
}

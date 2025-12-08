import { Navigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { LandingPage } from './LandingPage'
import { Spinner, Center } from '@chakra-ui/react'

export const LandingPageWrapper = () => {
  const { user, isLoading } = useAuth()

  // Show loading spinner while checking auth status
  if (isLoading) {
    return (
      <Center h="100vh">
        <Spinner size="xl" color="blue.500" thickness="4px" />
      </Center>
    )
  }

  // If user is authenticated, redirect to dashboard
  if (user) {
    return <Navigate to="/dashboard" replace />
  }

  // Otherwise show landing page
  return <LandingPage />
}

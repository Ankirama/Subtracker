import { Box, HStack, VStack, Text, Icon, useColorModeValue } from '@chakra-ui/react'
import { Link as RouterLink, useLocation } from 'react-router-dom'
import { FiHome, FiCreditCard, FiBell, FiUser } from 'react-icons/fi'

interface NavItem {
  label: string
  icon: any
  path: string
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: FiHome, path: '/dashboard' },
  { label: 'Subscriptions', icon: FiCreditCard, path: '/subscriptions' },
  { label: 'Notifications', icon: FiBell, path: '/notifications' },
  { label: 'Profile', icon: FiUser, path: '/settings/2fa' },
]

export const BottomNav = () => {
  const location = useLocation()
  const bgColor = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const activeColor = 'blue.500'
  const inactiveColor = useColorModeValue('gray.600', 'gray.400')

  return (
    <Box
      position="fixed"
      bottom={0}
      left={0}
      right={0}
      display={{ base: 'block', lg: 'none' }}
      bg={bgColor}
      borderTopWidth="1px"
      borderColor={borderColor}
      zIndex={1000}
      // Safe area support for notched devices
      pb="env(safe-area-inset-bottom)"
    >
      <HStack
        h="60px"
        justify="space-around"
        align="center"
        px={2}
      >
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname === item.path ||
                          (item.path === '/notifications' && location.pathname.startsWith('/notifications'))

          return (
            <Box
              key={item.path}
              as={RouterLink}
              to={item.path}
              flex={1}
              display="flex"
              justifyContent="center"
              alignItems="center"
              h="full"
              _hover={{ bg: useColorModeValue('gray.50', 'gray.700') }}
              transition="background 0.2s"
            >
              <VStack spacing={0.5} py={1}>
                <Icon
                  as={item.icon}
                  boxSize={6}
                  color={isActive ? activeColor : inactiveColor}
                  transition="color 0.2s"
                />
                <Text
                  fontSize="xs"
                  fontWeight={isActive ? 'bold' : 'normal'}
                  color={isActive ? activeColor : inactiveColor}
                  transition="all 0.2s"
                >
                  {item.label}
                </Text>
              </VStack>
            </Box>
          )
        })}
      </HStack>
    </Box>
  )
}

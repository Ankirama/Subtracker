import {
  Box,
  Flex,
  VStack,
  Text,
  Icon,
  Button,
  Avatar,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  useColorModeValue,
  Heading,
} from '@chakra-ui/react'
import { Link as RouterLink, useLocation, Outlet } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import {
  FiHome,
  FiCreditCard,
  FiMail,
  FiBarChart2,
  FiLogOut,
  FiUser,
  FiTool,
} from 'react-icons/fi'

interface NavItem {
  label: string
  icon: any
  path: string
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: FiHome, path: '/dashboard' },
  { label: 'Subscriptions', icon: FiCreditCard, path: '/subscriptions' },
  { label: 'Mailboxes', icon: FiMail, path: '/mailboxes' },
  { label: 'Analytics', icon: FiBarChart2, path: '/analytics' },
  { label: 'AI Sandbox', icon: FiTool, path: '/ai-sandbox' },
]

export const DashboardLayout = () => {
  const { user, logout } = useAuth()
  const location = useLocation()
  const bgColor = useColorModeValue('gray.50', 'gray.900')
  const sidebarBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  return (
    <Flex h="100vh" bg={bgColor}>
      {/* Sidebar */}
      <Box
        w="250px"
        bg={sidebarBg}
        borderRightWidth="1px"
        borderColor={borderColor}
        p={6}
      >
        <VStack align="stretch" spacing={6} h="full">
          {/* Logo */}
          <Box>
            <Heading size="md" color="blue.500">
              📧 SubTracker
            </Heading>
          </Box>

          {/* Navigation */}
          <VStack align="stretch" spacing={1} flex={1}>
            {NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <Button
                  key={item.path}
                  as={RouterLink}
                  to={item.path}
                  leftIcon={<Icon as={item.icon} />}
                  variant={isActive ? 'solid' : 'ghost'}
                  colorScheme={isActive ? 'blue' : 'gray'}
                  justifyContent="flex-start"
                  fontWeight={isActive ? 'bold' : 'normal'}
                >
                  {item.label}
                </Button>
              )
            })}
          </VStack>

          {/* User menu */}
          <Menu>
            <MenuButton
              as={Button}
              variant="outline"
              leftIcon={<Avatar size="sm" name={user?.email} />}
              w="full"
              textAlign="left"
            >
              <Text fontSize="sm" isTruncated>
                {user?.email}
              </Text>
            </MenuButton>
            <MenuList>
              <MenuItem icon={<Icon as={FiUser} />}>Profile</MenuItem>
              <MenuDivider />
              <MenuItem icon={<Icon as={FiLogOut} />} onClick={logout}>
                Logout
              </MenuItem>
            </MenuList>
          </Menu>
        </VStack>
      </Box>

      {/* Main content */}
      <Box flex={1} overflow="auto">
        <Outlet />
      </Box>
    </Flex>
  )
}

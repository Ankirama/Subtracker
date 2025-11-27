import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Icon,
  Button,
  IconButton,
  Avatar,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  useColorModeValue,
  useColorMode,
  Heading,
  Divider,
  Image,
} from '@chakra-ui/react'
import { Link as RouterLink, useLocation, Outlet } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { NotificationBell } from '../notifications/NotificationBell'
import { BottomNav } from '../navigation/BottomNav'
import {
  FiHome,
  FiCreditCard,
  FiMail,
  FiBarChart2,
  FiLogOut,
  FiUser,
  FiTool,
  FiShield,
  FiTrendingDown,
  FiDollarSign,
  FiTag,
  FiLock,
  FiAlertCircle,
  FiCopy,
  FiSettings,
  FiSun,
  FiMoon,
} from 'react-icons/fi'

interface NavItem {
  label: string
  icon: any
  path: string
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: FiHome, path: '/dashboard' },
  { label: 'Subscriptions', icon: FiCreditCard, path: '/subscriptions' },
  { label: 'Duplicates', icon: FiCopy, path: '/duplicates' },
  { label: 'Reviews', icon: FiAlertCircle, path: '/reviews' },
  { label: 'Categories', icon: FiTag, path: '/categories' },
  { label: 'Mailboxes', icon: FiMail, path: '/mailboxes' },
  { label: 'Budgets', icon: FiDollarSign, path: '/budgets' },
  { label: 'Analytics', icon: FiBarChart2, path: '/analytics' },
  { label: 'Optimize', icon: FiTrendingDown, path: '/optimize' },
  { label: 'AI Sandbox', icon: FiTool, path: '/ai-sandbox' },
]

export const DashboardLayout = () => {
  const { user, logout } = useAuth()
  const location = useLocation()
  const { colorMode, toggleColorMode } = useColorMode()
  const bgColor = useColorModeValue('gray.50', 'gray.900')
  const sidebarBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  return (
    <Flex h="100vh" bg={bgColor}>
      {/* Sidebar - Hidden on mobile */}
      <Box
        display={{ base: 'none', lg: 'block' }}
        w="250px"
        bg={sidebarBg}
        borderRightWidth="1px"
        borderColor={borderColor}
        p={6}
      >
        <VStack align="stretch" spacing={6} h="full">
          {/* Logo */}
          <Box as={RouterLink} to="/dashboard">
            <HStack spacing={3}>
              <Image
                src="/logo.png"
                alt="SubTracker Logo"
                h="40px"
                w="40px"
                objectFit="contain"
              />
              <Heading size="md" color="blue.500">
                SubTracker
              </Heading>
            </HStack>
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

            {/* Admin Panel - Only visible to admin users */}
            {user?.is_admin && (
              <>
                <Divider my={2} />
                <Button
                  as={RouterLink}
                  to="/admin/config"
                  leftIcon={<Icon as={FiShield} />}
                  variant={location.pathname.startsWith('/admin') ? 'solid' : 'ghost'}
                  colorScheme={location.pathname.startsWith('/admin') ? 'red' : 'gray'}
                  justifyContent="flex-start"
                  fontWeight={location.pathname.startsWith('/admin') ? 'bold' : 'normal'}
                >
                  Admin Panel
                </Button>
              </>
            )}
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
              <MenuItem icon={<Icon as={FiSettings} />} as={RouterLink} to="/settings">
                Settings
              </MenuItem>
              <MenuItem icon={<Icon as={FiLock} />} as={RouterLink} to="/settings/2fa">
                Two-Factor Auth
              </MenuItem>
              <MenuDivider />
              <MenuItem icon={<Icon as={FiLogOut} />} onClick={logout}>
                Logout
              </MenuItem>
            </MenuList>
          </Menu>
        </VStack>
      </Box>

      {/* Main content */}
      <Box
        flex={1}
        display="flex"
        flexDirection="column"
        overflow="hidden"
      >
        {/* Header with notification bell */}
        <Flex
          h="60px"
          px={{ base: 4, md: 6 }}
          bg={sidebarBg}
          borderBottomWidth="1px"
          borderColor={borderColor}
          align="center"
          justify={{ base: 'space-between', lg: 'flex-end' }}
          flexShrink={0}
        >
          {/* Logo on mobile only */}
          <Heading size="md" color="blue.500" display={{ base: 'block', lg: 'none' }}>
            📧 SubTracker
          </Heading>

          <HStack spacing={2}>
            {/* Color mode toggle */}
            <IconButton
              aria-label={`Switch to ${colorMode === 'light' ? 'dark' : 'light'} mode`}
              icon={<Icon as={colorMode === 'light' ? FiMoon : FiSun} />}
              onClick={toggleColorMode}
              variant="ghost"
              size="sm"
            />

            <NotificationBell />

            {/* User menu on mobile */}
            <Box display={{ base: 'block', lg: 'none' }}>
              <Menu>
                <MenuButton
                  as={Button}
                  variant="ghost"
                  size="sm"
                  p={0}
                >
                  <Avatar size="sm" name={user?.email} />
                </MenuButton>
                <MenuList>
                  <MenuItem icon={<Icon as={FiSettings} />} as={RouterLink} to="/settings">
                    Settings
                  </MenuItem>
                  <MenuItem icon={<Icon as={FiLock} />} as={RouterLink} to="/settings/2fa">
                    Two-Factor Auth
                  </MenuItem>
                  {user?.is_admin && (
                    <MenuItem
                      icon={<Icon as={FiShield} />}
                      as={RouterLink}
                      to="/admin/config"
                    >
                      Admin Panel
                    </MenuItem>
                  )}
                  <MenuDivider />
                  <MenuItem icon={<Icon as={FiLogOut} />} onClick={logout}>
                    Logout
                  </MenuItem>
                </MenuList>
              </Menu>
            </Box>
          </HStack>
        </Flex>

        {/* Page content */}
        <Box
          flex={1}
          overflow="auto"
          pb={{ base: '80px', lg: 0 }}
        >
          <Outlet />
        </Box>
      </Box>

      {/* Bottom Navigation - Mobile only */}
      <BottomNav />
    </Flex>
  )
}

import {
  Box,
  Container,
  Heading,
  Text,
  SimpleGrid,
  Image,
  VStack,
  useColorModeValue,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'

interface Screenshot {
  name: string
  image: string
  title: string
  description: string
}

export const AppShowcase = () => {
  const { t } = useTranslation()
  const bgColor = useColorModeValue('gray.50', 'gray.900')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  const screenshots: Screenshot[] = [
    {
      name: 'dashboard',
      image: '/screenshots/Dashboard.png',
      title: t('landing:showcase.dashboard.title'),
      description: t('landing:showcase.dashboard.description'),
    },
    {
      name: 'subscriptions',
      image: '/screenshots/Subscriptions.png',
      title: t('landing:showcase.subscriptions.title'),
      description: t('landing:showcase.subscriptions.description'),
    },
    {
      name: 'analytics',
      image: '/screenshots/Analytics.png',
      title: t('landing:showcase.analytics.title'),
      description: t('landing:showcase.analytics.description'),
    },
    {
      name: 'budgets',
      image: '/screenshots/Budgets.png',
      title: t('landing:showcase.budgets.title'),
      description: t('landing:showcase.budgets.description'),
    },
    {
      name: 'optimize',
      image: '/screenshots/Optimize.png',
      title: t('landing:showcase.optimize.title'),
      description: t('landing:showcase.optimize.description'),
    },
    {
      name: 'reviews',
      image: '/screenshots/Reviews.png',
      title: t('landing:showcase.reviews.title'),
      description: t('landing:showcase.reviews.description'),
    },
  ]

  return (
    <Box bg={bgColor} py={20}>
      <Container maxW="container.xl">
        <VStack spacing={12}>
          {/* Header */}
          <VStack spacing={4} textAlign="center">
            <Heading
              as="h2"
              fontSize={{ base: '3xl', md: '4xl', lg: '5xl' }}
              fontWeight="bold"
            >
              {t('landing:showcase.title')}
            </Heading>
            <Text
              fontSize={{ base: 'lg', md: 'xl' }}
              color="gray.600"
              _dark={{ color: 'gray.400' }}
              maxW="3xl"
            >
              {t('landing:showcase.subtitle')}
            </Text>
          </VStack>

          {/* Screenshots Tabs */}
          <Box w="full">
            <Tabs
              variant="soft-rounded"
              colorScheme="brand"
              isFitted
              size={{ base: 'sm', md: 'md' }}
            >
              <TabList
                mb={8}
                flexWrap="wrap"
                gap={2}
                justifyContent="center"
              >
                {screenshots.map((screenshot) => (
                  <Tab key={screenshot.name} _selected={{ bg: 'brand.500', color: 'white' }}>
                    {screenshot.title}
                  </Tab>
                ))}
              </TabList>

              <TabPanels>
                {screenshots.map((screenshot) => (
                  <TabPanel key={screenshot.name} p={0}>
                    <VStack spacing={6}>
                      {/* Screenshot Image */}
                      <Box
                        w="full"
                        borderRadius="xl"
                        overflow="hidden"
                        borderWidth="1px"
                        borderColor={borderColor}
                        boxShadow="2xl"
                      >
                        <Image
                          src={screenshot.image}
                          alt={screenshot.title}
                          w="full"
                          h="auto"
                          objectFit="contain"
                        />
                      </Box>

                      {/* Description */}
                      <Text
                        fontSize="lg"
                        color="gray.600"
                        _dark={{ color: 'gray.400' }}
                        textAlign="center"
                        maxW="2xl"
                      >
                        {screenshot.description}
                      </Text>
                    </VStack>
                  </TabPanel>
                ))}
              </TabPanels>
            </Tabs>
          </Box>
        </VStack>
      </Container>
    </Box>
  )
}

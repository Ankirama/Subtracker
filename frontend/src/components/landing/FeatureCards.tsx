import {
  Box,
  Container,
  Heading,
  Text,
  SimpleGrid,
  VStack,
  Icon,
  useColorModeValue,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import {
  FiCpu,
  FiTrendingUp,
  FiDollarSign,
  FiGlobe,
  FiCopy,
  FiXCircle,
} from 'react-icons/fi'

interface Feature {
  icon: any
  titleKey: string
  descriptionKey: string
}

const features: Feature[] = [
  {
    icon: FiCpu,
    titleKey: 'aiDetection.title',
    descriptionKey: 'aiDetection.description',
  },
  {
    icon: FiTrendingUp,
    titleKey: 'smartAnalytics.title',
    descriptionKey: 'smartAnalytics.description',
  },
  {
    icon: FiDollarSign,
    titleKey: 'budgetTracking.title',
    descriptionKey: 'budgetTracking.description',
  },
  {
    icon: FiGlobe,
    titleKey: 'multiCurrency.title',
    descriptionKey: 'multiCurrency.description',
  },
  {
    icon: FiCopy,
    titleKey: 'duplicateDetection.title',
    descriptionKey: 'duplicateDetection.description',
  },
  {
    icon: FiXCircle,
    titleKey: 'cancellationAssist.title',
    descriptionKey: 'cancellationAssist.description',
  },
]

export const FeatureCards = () => {
  const { t } = useTranslation()
  const cardBg = useColorModeValue('white', 'gray.800')
  const cardBorder = useColorModeValue('gray.200', 'gray.700')

  return (
    <Box py={20} bg={useColorModeValue('gray.50', 'gray.900')}>
      <Container maxW="container.xl">
        <VStack spacing={12}>
          <VStack spacing={4} textAlign="center">
            <Heading as="h2" size="2xl">
              {t('landing:features.title')}
            </Heading>
            <Text fontSize="lg" color="gray.600" _dark={{ color: 'gray.300' }} maxW="2xl">
              {t('landing:features.subtitle')}
            </Text>
          </VStack>

          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={8} w="full">
            {features.map((feature, index) => (
              <Box
                key={index}
                p={8}
                bg={cardBg}
                borderWidth="1px"
                borderColor={cardBorder}
                borderRadius="lg"
                shadow="sm"
                _hover={{ shadow: 'md', transform: 'translateY(-4px)' }}
                transition="all 0.3s"
              >
                <VStack align="start" spacing={4}>
                  <Icon
                    as={feature.icon}
                    boxSize={10}
                    color="blue.500"
                  />
                  <Heading as="h3" size="md">
                    {t(`landing:features.${feature.titleKey}`)}
                  </Heading>
                  <Text color="gray.600" _dark={{ color: 'gray.300' }}>
                    {t(`landing:features.${feature.descriptionKey}`)}
                  </Text>
                </VStack>
              </Box>
            ))}
          </SimpleGrid>
        </VStack>
      </Container>
    </Box>
  )
}

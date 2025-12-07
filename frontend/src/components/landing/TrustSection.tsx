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
import { FiLock, FiShield, FiEyeOff } from 'react-icons/fi'

interface TrustItem {
  icon: any
  titleKey: string
  descriptionKey: string
}

const trustItems: TrustItem[] = [
  {
    icon: FiLock,
    titleKey: 'encryption.title',
    descriptionKey: 'encryption.description',
  },
  {
    icon: FiShield,
    titleKey: 'privacy.title',
    descriptionKey: 'privacy.description',
  },
  {
    icon: FiEyeOff,
    titleKey: 'noTracking.title',
    descriptionKey: 'noTracking.description',
  },
]

export const TrustSection = () => {
  const { t } = useTranslation()
  const bgColor = useColorModeValue('blue.50', 'blue.900')

  return (
    <Box py={20} bg={bgColor}>
      <Container maxW="container.xl">
        <VStack spacing={12}>
          <VStack spacing={4} textAlign="center">
            <Heading as="h2" size="2xl">
              {t('landing:trust.title')}
            </Heading>
            <Text fontSize="lg" color="gray.600" _dark={{ color: 'gray.300' }} maxW="2xl">
              {t('landing:trust.subtitle')}
            </Text>
          </VStack>

          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={8} w="full">
            {trustItems.map((item, index) => (
              <VStack
                key={index}
                spacing={4}
                textAlign="center"
                p={6}
              >
                <Icon
                  as={item.icon}
                  boxSize={12}
                  color="blue.500"
                />
                <Heading as="h3" size="md">
                  {t(`landing:trust.${item.titleKey}`)}
                </Heading>
                <Text color="gray.600" _dark={{ color: 'gray.300' }}>
                  {t(`landing:trust.${item.descriptionKey}`)}
                </Text>
              </VStack>
            ))}
          </SimpleGrid>
        </VStack>
      </Container>
    </Box>
  )
}

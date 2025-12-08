import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  HStack,
  Icon,
  useColorModeValue,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import { FiMail, FiCpu, FiTrendingUp } from 'react-icons/fi'

interface Step {
  icon: any
  titleKey: string
  descriptionKey: string
}

const steps: Step[] = [
  {
    icon: FiMail,
    titleKey: 'step1.title',
    descriptionKey: 'step1.description',
  },
  {
    icon: FiCpu,
    titleKey: 'step2.title',
    descriptionKey: 'step2.description',
  },
  {
    icon: FiTrendingUp,
    titleKey: 'step3.title',
    descriptionKey: 'step3.description',
  },
]

export const HowItWorks = () => {
  const { t } = useTranslation()
  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  return (
    <Box py={20}>
      <Container maxW="container.xl">
        <VStack spacing={12}>
          <VStack spacing={4} textAlign="center">
            <Heading as="h2" size="2xl">
              {t('landing:howItWorks.title')}
            </Heading>
            <Text fontSize="lg" color="gray.600" _dark={{ color: 'gray.300' }} maxW="2xl">
              {t('landing:howItWorks.subtitle')}
            </Text>
          </VStack>

          <VStack spacing={0} w="full" align="stretch">
            {steps.map((step, index) => (
              <Box key={index} position="relative">
                <HStack
                  p={8}
                  bg={cardBg}
                  borderWidth="1px"
                  borderColor={borderColor}
                  borderRadius="lg"
                  spacing={6}
                  align="start"
                  position="relative"
                >
                  {/* Step number */}
                  <Box
                    bg="blue.500"
                    color="white"
                    borderRadius="full"
                    w={12}
                    h={12}
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                    fontWeight="bold"
                    fontSize="xl"
                    flexShrink={0}
                  >
                    {index + 1}
                  </Box>

                  {/* Icon */}
                  <Icon
                    as={step.icon}
                    boxSize={10}
                    color="blue.500"
                    flexShrink={0}
                  />

                  {/* Content */}
                  <VStack align="start" spacing={2} flex={1}>
                    <Heading as="h3" size="md">
                      {t(`landing:howItWorks.${step.titleKey}`)}
                    </Heading>
                    <Text color="gray.600" _dark={{ color: 'gray.300' }}>
                      {t(`landing:howItWorks.${step.descriptionKey}`)}
                    </Text>
                  </VStack>
                </HStack>

                {/* Connecting line (except for last step) */}
                {index < steps.length - 1 && (
                  <Box
                    position="absolute"
                    left="calc(2rem + 1.5rem)"
                    top="100%"
                    width="2px"
                    height="32px"
                    bg={borderColor}
                  />
                )}
              </Box>
            ))}
          </VStack>
        </VStack>
      </Container>
    </Box>
  )
}

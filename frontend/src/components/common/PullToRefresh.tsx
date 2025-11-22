import { ReactNode, useState, useRef, useEffect } from 'react'
import { motion, useMotionValue, useTransform, PanInfo } from 'framer-motion'
import { Box, Spinner, Text, VStack, useColorModeValue } from '@chakra-ui/react'

interface PullToRefreshProps {
  children: ReactNode
  onRefresh: () => Promise<void>
  threshold?: number
  disabled?: boolean
}

export const PullToRefresh = ({
  children,
  onRefresh,
  threshold = 80,
  disabled = false,
}: PullToRefreshProps) => {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [canPull, setCanPull] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const y = useMotionValue(0)

  const bgColor = useColorModeValue('gray.50', 'gray.800')
  const textColor = useColorModeValue('gray.600', 'gray.400')

  // Transform y position to opacity and scale for refresh indicator
  const opacity = useTransform(y, [0, threshold], [0, 1])
  const scale = useTransform(y, [0, threshold], [0.5, 1])

  // Check if we're at the top of the scrollable parent
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Find the nearest scrollable parent
    const findScrollableParent = (element: HTMLElement | null): HTMLElement | Window => {
      if (!element) return window
      const style = getComputedStyle(element)
      if (style.overflow === 'auto' || style.overflow === 'scroll' || style.overflowY === 'auto' || style.overflowY === 'scroll') {
        return element
      }
      return findScrollableParent(element.parentElement)
    }

    const scrollParent = findScrollableParent(container.parentElement)

    const handleScroll = () => {
      const scrollTop = scrollParent instanceof Window ? window.scrollY : scrollParent.scrollTop
      const isAtTop = scrollTop <= 0
      setCanPull(isAtTop)
    }

    scrollParent.addEventListener('scroll', handleScroll)
    handleScroll() // Check initial state

    return () => scrollParent.removeEventListener('scroll', handleScroll)
  }, [])

  const handleDragEnd = async (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    const offset = info.offset.y

    // Only trigger refresh if pulled down beyond threshold
    if (offset > threshold && canPull && !isRefreshing && !disabled) {
      setIsRefreshing(true)
      try {
        await onRefresh()
      } catch (error) {
        console.error('Refresh failed:', error)
      } finally {
        setIsRefreshing(false)
        y.set(0) // Reset position
      }
    }
  }

  return (
    <Box
      ref={containerRef}
      position="relative"
    >
      {/* Pull indicator */}
      <motion.div
        style={{
          position: 'absolute',
          top: -60,
          left: 0,
          right: 0,
          height: 60,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity,
          scale,
        }}
      >
        <VStack spacing={1}>
          {isRefreshing ? (
            <>
              <Spinner size="sm" color="blue.500" />
              <Text fontSize="xs" color={textColor}>
                Refreshing...
              </Text>
            </>
          ) : (
            <Text fontSize="xs" color={textColor}>
              Pull to refresh
            </Text>
          )}
        </VStack>
      </motion.div>

      {/* Content */}
      <motion.div
        drag={!disabled && canPull && !isRefreshing ? 'y' : false}
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={0.3}
        onDragEnd={handleDragEnd}
        style={{
          y: isRefreshing ? threshold / 2 : y,
          touchAction: 'pan-y',
        }}
        animate={{
          y: isRefreshing ? threshold / 2 : 0,
        }}
        transition={{
          type: 'spring',
          damping: 20,
          stiffness: 300,
        }}
      >
        {children}
      </motion.div>
    </Box>
  )
}

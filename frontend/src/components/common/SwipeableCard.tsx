import { ReactNode, useState } from 'react'
import { motion, PanInfo, useMotionValue, useTransform } from 'framer-motion'
import { Box, useColorModeValue } from '@chakra-ui/react'

interface SwipeableCardProps {
  children: ReactNode
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
  leftColor?: string
  rightColor?: string
  threshold?: number
}

export const SwipeableCard = ({
  children,
  onSwipeLeft,
  onSwipeRight,
  leftColor = '#3182ce', // blue.500
  rightColor = '#E53E3E', // red.500
  threshold = 100,
}: SwipeableCardProps) => {
  const [isDragging, setIsDragging] = useState(false)
  const x = useMotionValue(0)
  const bgColor = useColorModeValue('white', 'gray.800')

  // Transform x position to background color opacity
  const leftOpacity = useTransform(x, [-threshold, 0], [0.9, 0])
  const rightOpacity = useTransform(x, [0, threshold], [0, 0.9])

  const handleDragEnd = (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    setIsDragging(false)
    const offset = info.offset.x
    const velocity = info.velocity.x

    // Left swipe (negative offset)
    if (offset < -threshold || velocity < -500) {
      if (onSwipeLeft) {
        onSwipeLeft()
      }
    }
    // Right swipe (positive offset)
    else if (offset > threshold || velocity > 500) {
      if (onSwipeRight) {
        onSwipeRight()
      }
    }
  }

  return (
    <Box position="relative" overflow="hidden" borderRadius="md">
      {/* Left swipe indicator (Edit - Blue) */}
      <motion.div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          right: 0,
          backgroundColor: leftColor,
          opacity: leftOpacity,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          paddingRight: '20px',
          color: 'white',
          fontWeight: 'bold',
          fontSize: '18px',
          pointerEvents: 'none',
        }}
      >
        Edit →
      </motion.div>

      {/* Right swipe indicator (Delete - Red) */}
      <motion.div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          right: 0,
          backgroundColor: rightColor,
          opacity: rightOpacity,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-start',
          paddingLeft: '20px',
          color: 'white',
          fontWeight: 'bold',
          fontSize: '18px',
          pointerEvents: 'none',
        }}
      >
        ← Delete
      </motion.div>

      {/* Swipeable content */}
      <motion.div
        drag="x"
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.2}
        onDragStart={() => setIsDragging(true)}
        onDragEnd={handleDragEnd}
        style={{
          x,
          backgroundColor: bgColor,
          cursor: isDragging ? 'grabbing' : 'grab',
          touchAction: 'pan-y', // Allow vertical scrolling
        }}
        whileTap={{ scale: 0.98 }}
      >
        {children}
      </motion.div>
    </Box>
  )
}

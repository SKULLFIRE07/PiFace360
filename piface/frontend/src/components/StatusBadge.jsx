import React from 'react'

const variants = {
  in: {
    bg: 'bg-green-100 text-green-800',
    dot: 'bg-green-500',
    label: 'IN',
  },
  out: {
    bg: 'bg-gray-100 text-gray-700',
    dot: 'bg-gray-400',
    label: 'OUT',
  },
  break: {
    bg: 'bg-yellow-100 text-yellow-800',
    dot: 'bg-yellow-500',
    label: 'Break',
  },
  not_arrived: {
    bg: 'bg-red-100 text-red-800',
    dot: 'bg-red-500',
    label: 'Not Arrived',
  },
  on_leave: {
    bg: 'bg-blue-100 text-blue-800',
    dot: 'bg-blue-500',
    label: 'On Leave',
  },
  holiday: {
    bg: 'bg-purple-100 text-purple-800',
    dot: 'bg-purple-500',
    label: 'Holiday',
  },
}

export default function StatusBadge({ status, className = '' }) {
  const variant = variants[status] || variants.out
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${variant.bg} ${className}`}
      role="status"
      aria-label={variant.label}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${variant.dot}`} aria-hidden="true" />
      {variant.label}
    </span>
  )
}

import { createDarkTheme, createLightTheme } from '@fluentui/react-components'
import type { BrandVariants, Theme } from '@fluentui/react-components'

// A single harbour-blue ramp. The base brand colour sits at step 80.
const harbourBlue: BrandVariants = {
  10: '#03121F', 20: '#072035', 30: '#0B2B49', 40: '#0F365A', 50: '#134067',
  60: '#174974', 70: '#1B5282', 80: '#1F5C8B', 90: '#3F7099', 100: '#5A84AA',
  110: '#7597BA', 120: '#90AAC9', 130: '#ABBDD7', 140: '#C5D0E3', 150: '#DEE4EF', 160: '#F1F4F9',
}

const typography = {
  fontFamilyBase: "'Aptos', 'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, sans-serif",
  fontFamilyNumeric: "'Aptos', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif",
}

export const lightTheme: Theme = {
  ...createLightTheme(harbourBlue),
  ...typography,
  colorNeutralBackground2: '#F6F7F9',
  colorNeutralBackground3: '#EFF1F4',
}

export const darkTheme: Theme = {
  ...createDarkTheme(harbourBlue),
  ...typography,
  colorBrandForeground1: '#7597BA',
  colorBrandForeground2: '#90AAC9',
}

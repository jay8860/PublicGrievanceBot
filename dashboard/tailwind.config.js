/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            // "District register": warm paper neutrals + one ink accent.
            colors: {
                slate: {
                    50: '#faf9f7', 100: '#f4f2ed', 200: '#e7e3da', 300: '#d6d0c4',
                    400: '#a9a29a', 500: '#7e776f', 600: '#5f5951', 700: '#474139',
                    800: '#302b25', 900: '#1c1814', 950: '#12100d',
                },
                blue: {
                    50: '#f3f6f9', 100: '#e4ebf2', 200: '#c8d7e5', 300: '#9db6cd',
                    400: '#6d8dab', 500: '#486a8b', 600: '#325377', 700: '#27425f',
                    800: '#1e344a', 900: '#162738', 950: '#0f1c29',
                },
                emerald: {
                    50: '#f2f6f2', 100: '#e2ece3', 200: '#c5d9c7', 300: '#9dbca1',
                    400: '#748f78', 500: '#557059', 600: '#415b45', 700: '#334a37',
                    800: '#2a3c2d', 900: '#1e2b21',
                },
                green: {
                    50: '#f2f6f2', 100: '#e2ece3', 200: '#c5d9c7', 300: '#9dbca1',
                    400: '#748f78', 500: '#557059', 600: '#415b45', 700: '#334a37',
                    800: '#2a3c2d', 900: '#1e2b21',
                },
                amber: {
                    50: '#faf6ee', 100: '#f4ebd9', 200: '#e7d4ae', 300: '#d3b97f',
                    400: '#b89a58', 500: '#967a3d', 600: '#7a6230', 700: '#5f4c26',
                    800: '#4a3c1f', 900: '#332a16',
                },
                orange: {
                    50: '#fbf4f0', 100: '#f6e5db', 200: '#ebc9b4', 300: '#d9a486',
                    400: '#bf8060', 500: '#9d6347', 600: '#7f4f38', 700: '#663f2d',
                    800: '#4f3123', 900: '#38231a',
                },
                red: {
                    50: '#fbf3f2', 100: '#f6e2df', 200: '#ebc4bf', 300: '#d99b93',
                    400: '#bf7064', 500: '#9d5145', 600: '#7f3f36', 700: '#66332c',
                    800: '#4f2822', 900: '#381c18',
                },
                rose: {
                    50: '#fbf3f2', 100: '#f6e2df', 200: '#ebc4bf', 300: '#d99b93',
                    400: '#bf7064', 500: '#9d5145', 600: '#7f3f36', 700: '#66332c',
                    800: '#4f2822', 900: '#381c18',
                },
                sky: {
                    50: '#f2f6f8', 100: '#e3edf2', 200: '#c6dae4', 300: '#9cbdcb',
                    400: '#6d95a5', 500: '#4b7484', 600: '#375d6b', 700: '#2c4b56',
                    800: '#243b45', 900: '#1a2b33',
                },
                indigo: {
                    50: '#f3f5f9', 100: '#e5e9f2', 200: '#cbd3e3', 300: '#a3b0c9',
                    400: '#7787a6', 500: '#546686', 600: '#3e4f6b', 700: '#324056',
                    800: '#283345', 900: '#1d2634',
                },
                violet: {
                    50: '#f5f4f8', 100: '#eae7f0', 200: '#d6d0e1', 300: '#b3a9c7',
                    400: '#8a7da4', 500: '#665984', 600: '#4d4367', 700: '#3e3653',
                    800: '#332c44', 900: '#252031',
                },
            },
            fontFamily: {
                sans: ['ui-sans-serif', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
                serif: ['Iowan Old Style', 'Palatino Linotype', 'Palatino', 'Georgia', 'serif'],
                mono: ['ui-monospace', 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'monospace'],
            },
            borderRadius: {
                none: '0', sm: '2px', DEFAULT: '3px', md: '4px', lg: '4px', xl: '6px', '2xl': '8px',
            },
            boxShadow: {
                sm: '0 1px 0 0 rgb(28 24 20 / 0.04)',
                DEFAULT: '0 1px 2px 0 rgb(28 24 20 / 0.06)',
                md: '0 2px 4px -1px rgb(28 24 20 / 0.08)',
            },
            letterSpacing: {
                wide: '0.01em', wider: '0.02em', widest: '0.03em',
            },
        },
    },
    plugins: [],
}


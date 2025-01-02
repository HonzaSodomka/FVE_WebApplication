/** @type {import('next').NextConfig} */
const nextConfig = {
    env: {
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || (
        process.env.NODE_ENV === 'production' 
          ? 'http://bijec.nti.tul.cz:8000'
          : 'http://localhost:8000'
      ),
      NEXT_PUBLIC_TEST: 'Toto je testovací proměnná'
    }
  };
  
  module.exports = nextConfig;
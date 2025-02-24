const DEBUG = import.meta.env.MODE === 'development';

export const logger = {
  error: (message: string, error?: any) => {
    console.error(message, error);
  },
  info: (message: string, data?: any) => {
    console.info(message, data);
  },
  warn: (message: string, data?: any) => {
    console.warn(message, data);
  },
  debug: (...args: any[]) => {
    if (DEBUG) console.debug('[DEBUG]', ...args);
  }
}; 
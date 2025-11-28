import { appendFileSync, existsSync, mkdirSync } from 'fs';
import { dirname } from 'path';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: Record<string, unknown>;
}

class Logger {
  private logPath: string | null = null;
  private minLevel: LogLevel = 'debug';
  
  private readonly levelPriority: Record<LogLevel, number> = {
    debug: 0,
    info: 1,
    warn: 2,
    error: 3
  };

  init(logPath?: string, minLevel: LogLevel = 'debug') {
    this.minLevel = minLevel;
    
    if (logPath) {
      this.logPath = logPath;
      const dir = dirname(logPath);
      
      if (!existsSync(dir)) {
        try {
          mkdirSync(dir, { recursive: true });
        } catch (err) {
          console.error(`[LOGGER] Failed to create log directory ${dir}:`, err);
          this.logPath = null;
        }
      }
      
      if (this.logPath) {
        this.info('Logger initialized', { logPath, minLevel });
      }
    }
  }

  private shouldLog(level: LogLevel): boolean {
    return this.levelPriority[level] >= this.levelPriority[this.minLevel];
  }

  private formatEntry(entry: LogEntry): string {
    const contextStr = entry.context 
      ? '  ' + JSON.stringify(entry.context, this.safeStringify, 2).replace(/\n/g, '\n  ')
      : '';
    return `[${entry.timestamp}] [${entry.level.toUpperCase().padEnd(5)}] ${entry.message}${contextStr ? '\n' + contextStr : ''}`;
  }

  private safeStringify(key: string, value: unknown): unknown {
    if (typeof value === 'string' && value.length > 1000) {
      return value.substring(0, 1000) + `... [truncated ${value.length - 1000} chars]`;
    }
    if (value instanceof Error) {
      return {
        name: value.name,
        message: value.message,
        stack: value.stack?.split('\n').slice(0, 10).join('\n')
      };
    }
    return value;
  }

  private log(level: LogLevel, message: string, context?: Record<string, unknown>) {
    if (!this.shouldLog(level)) return;

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      context
    };

    const formatted = this.formatEntry(entry);
    
    // Console output with color
    const colors: Record<LogLevel, string> = {
      debug: '\x1b[90m',  // gray
      info: '\x1b[36m',   // cyan
      warn: '\x1b[33m',   // yellow
      error: '\x1b[31m'   // red
    };
    const reset = '\x1b[0m';
    console.log(`${colors[level]}${formatted}${reset}`);
    
    // File output
    if (this.logPath) {
      try {
        appendFileSync(this.logPath, formatted + '\n');
      } catch (err) {
        console.error(`[LOGGER] Failed to write to log file:`, err);
      }
    }
  }

  debug(message: string, context?: Record<string, unknown>) {
    this.log('debug', message, context);
  }

  info(message: string, context?: Record<string, unknown>) {
    this.log('info', message, context);
  }

  warn(message: string, context?: Record<string, unknown>) {
    this.log('warn', message, context);
  }

  error(message: string, context?: Record<string, unknown>) {
    this.log('error', message, context);
  }

  // Specialized logging methods for common scenarios

  request(method: string, path: string, context?: Record<string, unknown>) {
    this.info(`→ ${method} ${path}`, context);
  }

  response(method: string, path: string, status: number, durationMs: number, context?: Record<string, unknown>) {
    const level: LogLevel = status >= 500 ? 'error' : status >= 400 ? 'warn' : 'info';
    this.log(level, `← ${method} ${path} ${status} (${durationMs}ms)`, context);
  }

  mongerRequest(endpoint: string, context?: Record<string, unknown>) {
    this.info(`Monger Request: ${endpoint}`, context);
  }

  mongerResponse(endpoint: string, durationMs: number, context?: Record<string, unknown>) {
    this.info(`Monger Response: ${endpoint}`, { durationMs, ...context });
  }

  mongerError(error: Error | unknown, context?: Record<string, unknown>) {
    const errorInfo = error instanceof Error 
      ? { 
          name: error.name, 
          message: error.message,
          cause: (error as any).cause,
          code: (error as any).code,
          status: (error as any).status,
          stack: error.stack?.split('\n').slice(0, 5).join('\n')
        }
      : { error: String(error) };
    
    this.error(`Monger Service Error`, { ...errorInfo, ...context });
  }

  session(action: string, sessionId: string, customerId?: string, context?: Record<string, unknown>) {
    this.info(`Session: ${action}`, { sessionId: sessionId.substring(0, 8) + '...', customerId: customerId?.substring(0, 8) + '...', ...context });
  }

  shopify(action: string, context?: Record<string, unknown>) {
    this.info(`Shopify: ${action}`, context);
  }

  shopifyError(action: string, error: Error | unknown, context?: Record<string, unknown>) {
    const errorInfo = error instanceof Error 
      ? { name: error.name, message: error.message }
      : { error: String(error) };
    this.error(`Shopify Error: ${action}`, { ...errorInfo, ...context });
  }
}

// Singleton instance
export const logger = new Logger();


import { useState } from 'react';
import { cn } from '@/lib/utils';

interface SubTab {
  id: string;
  label: string;
  component: React.ComponentType;
  icon?: React.ComponentType<{ className?: string }>;
}

interface SubTabsProps {
  tabs: SubTab[];
  defaultTab?: string;
  className?: string;
  tabClassName?: string;
  contentClassName?: string;
}

export function SubTabs({ 
  tabs, 
  defaultTab, 
  className,
  tabClassName,
  contentClassName 
}: SubTabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id);

  const ActiveComponent = tabs.find(tab => tab.id === activeTab)?.component;

  if (!ActiveComponent) {
    return (
      <div className="flex items-center justify-center p-8 text-muted-foreground">
        No content available
      </div>
    );
  }

  return (
    <div className={cn("w-full", className)}>
      {/* Tab Navigation */}
      <div className="border-b border-border">
        <nav className="flex space-x-8 px-6" aria-label="Sub-tabs">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            const Icon = tab.icon;
            
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
                  tabClassName
                )}
                aria-current={isActive ? "page" : undefined}
              >
                {Icon && <Icon className="h-4 w-4" />}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className={cn("py-6", contentClassName)}>
        <ActiveComponent />
      </div>
    </div>
  );
}

export type { SubTab, SubTabsProps };
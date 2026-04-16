import { HeaderBar } from "./HeaderBar";
import { StatusBar } from "./StatusBar";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen flex-col">
      <HeaderBar />
      <main className="flex-1 bg-evlos-700 dark:bg-evlos-800 overflow-hidden">
        <div className="bg-background rounded-t-lg mx-4 h-full flex flex-col">
          {children}
        </div>
      </main>
      <StatusBar />
    </div>
  );
}

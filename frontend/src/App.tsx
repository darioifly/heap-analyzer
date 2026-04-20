import { Layout } from "@/components/layout/Layout";
import { MainLayout } from "@/components/layout/MainLayout";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function App() {
  return (
    <ErrorBoundary>
      <Layout>
        <MainLayout />
      </Layout>
    </ErrorBoundary>
  );
}

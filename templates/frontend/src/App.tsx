import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <main className="min-h-screen bg-gray-50 p-8">
        <h1 className="text-3xl font-bold">myapp</h1>
      </main>
    </QueryClientProvider>
  );
}

import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

import LoginPage from "@/pages/LoginPage";
import SignupPage from "@/pages/SignupPage";
import VerifyEmailPage from "@/pages/VerifyEmailPage";
import DashboardPage from "@/pages/DashboardPage";
import InstancesPage from "@/pages/InstancesPage";
import JobsPage from "@/pages/JobsPage";
import NewJobPage from "@/pages/NewJobPage";
import JobDetailPage from "@/pages/JobDetailPage";
import SolutionsPage from "@/pages/SolutionsPage";
import SolutionDetailPage from "@/pages/SolutionDetailPage";
import FleetPage from "@/pages/FleetPage";
import UsersPage from "@/pages/UsersPage";
import OrdersPage from "@/pages/OrdersPage";
import ProfilePage from "@/pages/ProfilePage";
import AlgorithmsPage from "@/pages/AlgorithmsPage";
import MetricsPage from "@/pages/MetricsPage";
import ComparisonPage from "@/pages/ComparisonPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireAlgoTester({ children }: { children: React.ReactNode }) {
  const { isAlgoTester } = useAuth();
  if (!isAlgoTester) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireDatasetProvider({ children }: { children: React.ReactNode }) {
  const { isDatasetProvider } = useAuth();
  if (!isDatasetProvider) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireMetricProvider({ children }: { children: React.ReactNode }) {
  const { isMetricProvider } = useAuth();
  if (!isMetricProvider) return <Navigate to="/" replace />;
  return <>{children}</>;
}

// legacy aliases
const RequireResearcher = RequireAlgoTester;
const RequireManager = RequireAdmin;

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />

      <Route
        path="/"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />

      <Route
        path="/instances"
        element={
          <RequireAuth>
            <InstancesPage />
          </RequireAuth>
        }
      />

      <Route
        path="/jobs"
        element={
          <RequireAuth>
            <RequireResearcher>
              <JobsPage />
            </RequireResearcher>
          </RequireAuth>
        }
      />
      <Route
        path="/jobs/new"
        element={
          <RequireAuth>
            <RequireResearcher>
              <NewJobPage />
            </RequireResearcher>
          </RequireAuth>
        }
      />
      <Route
        path="/jobs/:id"
        element={
          <RequireAuth>
            <RequireResearcher>
              <JobDetailPage />
            </RequireResearcher>
          </RequireAuth>
        }
      />

      <Route
        path="/solutions"
        element={
          <RequireAuth>
            <RequireResearcher>
              <SolutionsPage />
            </RequireResearcher>
          </RequireAuth>
        }
      />
      <Route
        path="/solutions/:id"
        element={
          <RequireAuth>
            <RequireResearcher>
              <SolutionDetailPage />
            </RequireResearcher>
          </RequireAuth>
        }
      />

      <Route
        path="/fleet"
        element={
          <RequireAuth>
            <RequireResearcher>
              <FleetPage />
            </RequireResearcher>
          </RequireAuth>
        }
      />

      <Route
        path="/users"
        element={
          <RequireAuth>
            <RequireManager>
              <UsersPage />
            </RequireManager>
          </RequireAuth>
        }
      />

      <Route
        path="/orders"
        element={
          <RequireAuth>
            <OrdersPage />
          </RequireAuth>
        }
      />

      <Route
        path="/algorithms"
        element={
          <RequireAuth>
            <RequireAlgoTester>
              <AlgorithmsPage />
            </RequireAlgoTester>
          </RequireAuth>
        }
      />

      <Route
        path="/metrics"
        element={
          <RequireAuth>
            <RequireMetricProvider>
              <MetricsPage />
            </RequireMetricProvider>
          </RequireAuth>
        }
      />

      <Route
        path="/comparison"
        element={
          <RequireAuth>
            <RequireResearcher>
              <ComparisonPage />
            </RequireResearcher>
          </RequireAuth>
        }
      />

      <Route
        path="/profile"
        element={
          <RequireAuth>
            <ProfilePage />
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

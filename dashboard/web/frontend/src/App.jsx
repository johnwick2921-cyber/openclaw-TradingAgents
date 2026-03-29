import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import LiveRun from './pages/LiveRun';
import RunDetails from './pages/RunDetails';
import CompareView from './pages/CompareView';
import Memories from './pages/Memories';
import Settings from './pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/runs/:id/live" element={<LiveRun />} />
        <Route path="/runs/:id" element={<RunDetails />} />
        <Route path="/runs/:id/compare/:id2" element={<CompareView />} />
        <Route path="/memories" element={<Memories />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

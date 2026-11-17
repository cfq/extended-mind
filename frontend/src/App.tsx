import { Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { SAVE_PATH } from "./lib/bookmarklet";
import { Add } from "./pages/Add";
import { Dashboard } from "./pages/Dashboard";
import { ItemPage } from "./pages/ItemPage";
import { Login } from "./pages/Login";
import { Logout } from "./pages/Logout";
import { NotFound } from "./pages/NotFound";
import { Profile } from "./pages/Profile";
import { Save } from "./pages/Save";
import { Settings } from "./pages/Settings";
import { Signup } from "./pages/Signup";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/logout" element={<Logout />} />
      <Route element={<RequireAuth />}>
        <Route path={SAVE_PATH} element={<Save />} />
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/add" element={<Add />} />
          <Route path="/item/:id" element={<ItemPage />} />
          <Route path="/user/:username" element={<Profile />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}

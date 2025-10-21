import { Navigate } from "react-router-dom";

const Index = () => {
  // Redirect to main app (this page isn't used since we have App.tsx as main component)
  return <Navigate to="/" replace />;
};

export default Index;

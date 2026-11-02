import { useSession } from "../lib/auth";

export function Home() {
  const { data: user } = useSession();

  return <h1>Welcome {user?.username}</h1>;
}

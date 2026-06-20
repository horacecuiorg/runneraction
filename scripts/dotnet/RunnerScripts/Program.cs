using System;

namespace RunnerScripts
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.WriteLine("==================================================");
            Console.WriteLine(" .NET Runner Action Script Starting");
            Console.WriteLine("==================================================");

            // Accessing command-line arguments
            string targetName = args.Length > 0 ? args[0] : "World";
            Console.WriteLine($"Greeting: Hello, {targetName}!");

            // Checking GitHub Actions environment variables
            string? isGitHubAction = Environment.GetEnvironmentVariable("GITHUB_ACTIONS");
            if (!string.IsNullOrEmpty(isGitHubAction) && isGitHubAction.Equals("true", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("Environment: Running inside GitHub Actions workflow.");
                string? repo = Environment.GetEnvironmentVariable("GITHUB_REPOSITORY");
                string? actor = Environment.GetEnvironmentVariable("GITHUB_ACTOR");
                Console.WriteLine($"Repository: {repo}");
                Console.WriteLine($"Triggered by: {actor}");
            }
            else
            {
                Console.WriteLine("Environment: Running locally.");
            }

            Console.WriteLine("==================================================");
            Console.WriteLine(" .NET Runner Action Script Completed Successfully");
            Console.WriteLine("==================================================");
            
            return 0; // Success exit code
        }
    }
}

Using Variables
Variables provide a way to manage configuration and secrets across services in Railway.

When defined, they are made available to your application as environment variables in the following scenarios:

The build process for each service deployment.
The running service deployment.
The command invoked by railway run <COMMAND>
The local shell via railway shell
In Railway, there is also a notion of configuration variables which allow you to control the behavior of the platform.

Adding, updating, or removing variables, results in a set of staged changes that you must review and deploy, in order to apply them.

Service Variables
Variables scoped to individual services can be defined by navigating to a service's "Variables" tab.

Screenshot of Variables Pane
Define a Service Variable
From a service's variables tab, click on New Variable to enter your variable into a form field, or use the RAW Editor to paste the contents of your .env or json-formatted file.

Shared Variables
Shared variables help reduce duplication of variables across multiple services within the same project.

Screenshot of Shared Variables Settings
Define a Shared Variable
From your Project Settings -> Shared Variables page, choose the Environment, enter the variable name and value, and click Add.

Use a Shared Variable
To use a shared variable, either click the Share button from the Project Settings -> Shared Variables menu and select the services with which to share, or visit the Variables tab within the service itself and click "Shared Variable".

Adding a shared variables to a service creates a Reference Variable in the service.

Reference Variables
Reference variables are those defined by referencing variables in other services, shared variables, or even variables in the same service.

When using reference variables, you also have access to Railway-provided variables.

Railway's template syntax is used when defining reference variables.

Referencing a Shared Variable
Use the following syntax to reference a shared variable:

${{ shared.VARIABLE_KEY }}
Example
Referencing Another Service's Variable
Use the following syntax to reference variables in another service:

${{SERVICE_NAME.VAR}}
Example
Referencing Variables in the Same Service
Use the following syntax to reference variables in the same service:

${{ VARIABLE_NAME }}
Example
You have the variables needed to construct an API endpoint already defined in your service - BASE_URL and AUTH_PATH - and you would like to combine them to create a single variable. Go to your service variables and add a new variable referencing other variables in the same service -
AUTH_ENDPOINT=https://${{ BASE_URL }}/${{ AUTH_PATH }}
Autocomplete Dropdown
The Railway dashboard provides an autocomplete dropdown in both the name and value fields to help create reference variables.

Screenshot of Variables Pane
Sealed Variables
Railway provides the ability to seal variable values for extra security. When a variable is sealed, its value is provided to builds and deployments but is never visible in the UI nor can it be retrieved via the API.

Sealing a Variable
To seal an existing variable, click the 3-dot menu on the right-side of the variable and choose the "Seal" option.

Seal an existing variable
Updating a Sealed Variable
Sealed variables can be updated by clicking the edit option in the 3-dot menu just like normal variables but they cannot be updated via the Raw Editor.

Caveats
Sealed variables are a security-first feature and with that come some constraints:

Sealed variables cannot be un-sealed.
Sealed variable values are not provided when using railway variables or railway run via the CLI.
Sealed variables are not copied over when creating PR environments.
Sealed variables are not copied when duplicating an environment.
Sealed variables are not copied when duplicating a service.
Sealed variables are not shown as part of the diff when syncing environment changes.
Sealed variables are not synced with external integrations.
Railway-provided Variables
Railway provides many variables to help with development operations. Some of the commonly used variables include -

RAILWAY_PUBLIC_DOMAIN
RAILWAY_PRIVATE_DOMAIN
RAILWAY_TCP_PROXY_PORT
For an exhaustive list, please check out the Variables Reference page.

Multiline Variables
Variables can span multiple lines. Press Control + Enter (Cmd + Enter on Mac) in the variable value input field to add a newline, or simply type a newline in the Raw Editor.

Using Variables in Your Services
Variables are made available at runtime as environment variables. To use them in your application, simply use the interface appropriate for your language to retrieve environment variables.

For example, in a node app -

process.env.VARIABLE_NAME;
Local Development
Using the Railway CLI, you can run your code locally with the environment variables configured in your Railway project.

Ensure that you have the Railway CLI installed and linked to your project
In your terminal, execute railway run <run command> -> for example, railway run npm run dev
Check out the CLI guide for more information on using the CLI.

Using Variables in your Dockerfile
For information on how to use variables in your Dockerfile refer to the Dockerfiles guide.
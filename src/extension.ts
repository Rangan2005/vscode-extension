// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import * as path from 'path';
import * as cp from 'child_process';
import { LanguageClient } from 'vscode-languageclient/node';
import { registerLogger, traceError, traceLog, traceVerbose } from './common/log/logging';
import {
    checkVersion,
    getInterpreterDetails,
    initializePython,
    onDidChangePythonInterpreter,
    resolveInterpreter,
} from './common/python';
import { restartServer } from './common/server';
import { checkIfConfigurationChanged, getInterpreterFromSetting } from './common/settings';
import { loadServerDefaults } from './common/setup';
import { getLSClientTraceLevel } from './common/utilities';
import { createOutputChannel, onDidChangeConfiguration, registerCommand } from './common/vscodeapi';

let lsClient: LanguageClient | undefined;
export async function activate(context: vscode.ExtensionContext): Promise<void> {
    // This is required to get server name and module. This should be
    // the first thing that we do in this extension.
    const serverInfo = loadServerDefaults();
    const serverName = serverInfo.name;
    const serverId = serverInfo.module;

    // Setup logging
    const outputChannel = createOutputChannel(serverName);
    context.subscriptions.push(outputChannel, registerLogger(outputChannel));

    const changeLogLevel = async (c: vscode.LogLevel, g: vscode.LogLevel) => {
        const level = getLSClientTraceLevel(c, g);
        await lsClient?.setTrace(level);
    };

    // context.subscriptions.push(
    //     outputChannel.onDidChangeLogLevel(async (e) => {
    //         await changeLogLevel(e, vscode.env.logLevel);
    //     }),
    //     vscode.env.onDidChangeLogLevel(async (e) => {
    //         await changeLogLevel(outputChannel.logLevel, e);
    //     }),
    // );

    context.subscriptions.push(
        vscode.commands.registerCommand('analyse.analyzeFunctions', async () => {
            // 1. Ask the user to select a folder
            const folderUris = await vscode.window.showOpenDialog({
                canSelectFolders: true,
                canSelectMany: false,
                openLabel: 'Select folder to analyze',
            });
            if (!folderUris || folderUris.length === 0) {
                return;
            }
            const folderPath = folderUris[0].fsPath;

            // 2. Determine the Python script path
            const scriptPath = path.join(context.extensionPath, 'pythonFiles', 'analyze_functions.py');

            // 3. Spawn Python subprocess
            //    Note: You may want to allow configuration of the python executable via settings.
            const pythonExec = 'python'; // or fetch from setting, e.g., vscode.workspace.getConfiguration('function-analyzer').get('pythonPath')
            const proc = cp.spawn(pythonExec, [scriptPath, folderPath]);

            let stdout = '';
            let stderr = '';
            proc.stdout.on('data', (data) => {
                stdout += data.toString();
            });
            proc.stderr.on('data', (data) => {
                stderr += data.toString();
            });
            proc.on('error', (err) => {
                vscode.window.showErrorMessage(`Failed to launch Python: ${err.message}`);
            });
            proc.on('close', () => {
                if (stderr) {
                    console.error(stderr);
                }
                let parsed: Record<string, number> = {};
                try {
                    parsed = JSON.parse(stdout);
                } catch (e) {
                    vscode.window.showErrorMessage('Could not parse analysis result from Python script.');
                    return;
                }
                if (parsed.error) {
                    vscode.window.showErrorMessage(`Analysis error: ${parsed.error}`);
                    return;
                }
                showFunctionCountWebview(parsed, folderPath);
            });
        }),
    );

    function showFunctionCountWebview(data: Record<string, number>, baseFolder: string) {
        const panel = vscode.window.createWebviewPanel(
            'functionCountAnalysis', // internal viewType
            'Function Count Analysis', // title
            vscode.ViewColumn.One,
            {
                enableScripts: false,
            },
        );
        // Build a nested tree-style HTML. For simplicity: sort entries alphabetically.
        const entries = Object.entries(data).sort((a, b) => a[0].localeCompare(b[0]));
        // Group by folder for display:
        interface TreeNode {
            [key: string]: TreeNode | number;
        }
        const tree: TreeNode = {};
        for (const [relPath, count] of entries) {
            const parts = relPath.split(path.sep);
            let curr: TreeNode = tree;
            for (let i = 0; i < parts.length; i++) {
                const part = parts[i];
                if (i === parts.length - 1) {
                    curr[part] = count;
                } else {
                    if (!(part in curr)) {
                        curr[part] = {};
                    }
                    curr = curr[part] as TreeNode;
                }
            }
        }
        // Recursive HTML builder:
        function buildList(node: TreeNode): string {
            let html = '<ul>';
            for (const key of Object.keys(node)) {
                const val = node[key];
                if (typeof val === 'number') {
                    html += `<li>${key}: ${val} function${val !== 1 ? 's' : ''}</li>`;
                } else {
                    html += `<li>${key}/${buildList(val)}</li>`;
                }
            }
            html += '</ul>';
            return html;
        }
        const bodyHtml = buildList(tree);
        panel.webview.html = `<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
        body { font-family: sans-serif; padding: 10px; }
        ul { list-style-type: none; padding-left: 1em; }
        li::before { content: "• "; color: #888; }
        </style>
    </head>
    <body>
        <h2>Function Count Analysis for:</h2>
        <p><strong>${baseFolder}</strong></p>
        ${bodyHtml}
    </body>
    </html>`;
    }

    // Log Server information
    traceLog(`Name: ${serverInfo.name}`);
    traceLog(`Module: ${serverInfo.module}`);
    traceVerbose(`Full Server Info: ${JSON.stringify(serverInfo)}`);

    const runServer = async () => {
        const interpreter = getInterpreterFromSetting(serverId);
        if (interpreter && interpreter.length > 0) {
            if (checkVersion(await resolveInterpreter(interpreter))) {
                traceVerbose(`Using interpreter from ${serverInfo.module}.interpreter: ${interpreter.join(' ')}`);
                lsClient = await restartServer(serverId, serverName, outputChannel, lsClient);
            }
            return;
        }

        const interpreterDetails = await getInterpreterDetails();
        if (interpreterDetails.path) {
            traceVerbose(`Using interpreter from Python extension: ${interpreterDetails.path.join(' ')}`);
            lsClient = await restartServer(serverId, serverName, outputChannel, lsClient);
            return;
        }

        traceError(
            'Python interpreter missing:\r\n' +
                '[Option 1] Select python interpreter using the ms-python.python.\r\n' +
                `[Option 2] Set an interpreter using "${serverId}.interpreter" setting.\r\n` +
                'Please use Python 3.8 or greater.',
        );
    };

    context.subscriptions.push(
        onDidChangePythonInterpreter(async () => {
            await runServer();
        }),
        onDidChangeConfiguration(async (e: vscode.ConfigurationChangeEvent) => {
            if (checkIfConfigurationChanged(e, serverId)) {
                await runServer();
            }
        }),
        registerCommand(`${serverId}.restart`, async () => {
            await runServer();
        }),
    );

    setImmediate(async () => {
        const interpreter = getInterpreterFromSetting(serverId);
        if (interpreter === undefined || interpreter.length === 0) {
            traceLog(`Python extension loading`);
            await initializePython(context.subscriptions);
            traceLog(`Python extension loaded`);
        } else {
            await runServer();
        }
    });
}

export async function deactivate(): Promise<void> {
    if (lsClient) {
        await lsClient.stop();
    }
}

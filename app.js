const serverHost = "http://localhost"; // Replace with your server host
const serverPort = 12345; // Replace with your server port
const messagesElement = document.getElementById("messages");
const messageInputElement = document.getElementById("message-input");
const sendButton = document.getElementById("send-btn");

let lastTimestamp = null;

// Initialize the SpeechSynthesis API
const synth = window.speechSynthesis;

// Define voice settings for upstream and downstream messages
const upstreamVoiceSettings = {
    voice: "en-US",
    rate: 1,
    pitch: 1,
};
const downstreamVoiceSettings = {
    voice: "en-GB",
    rate: 1,
    pitch: 1,
};
const redBeadVoiceSettings = {
    voice: "en-US",
    rate: 1.2,
    pitch: 1.1,
};
const blueBeadVoiceSettings = {
    voice: "en-AU",
    rate: 1.2,
    pitch: 0.9,
};
const userVoiceSettings = {
    voice: "en-IN",
    rate: 1.1,
    pitch: 0.9,
};

sendButton.addEventListener("click", () => {
    const userMessage = messageInputElement.value;
    if (userMessage.includes("@")) {
        const targetAgent = userMessage.split("@")[1].split(" ")[0];
        sendMessage(targetAgent, userMessage);
        messageInputElement.value = ""; // Clear the message input after sending

        // Add the user's message to the chat box
        const messageElement = document.createElement("div");
        messageElement.className = "message user-message";
        messageElement.textContent = `You: ${userMessage}`;
        messagesElement.appendChild(messageElement);
        messagesElement.scrollTop = messagesElement.scrollHeight; // Scroll to the bottom of the chat
    } else {
        alert("Please mention an agent using '@' followed by the agent id.");
    }
});

async function fetchMessages() {
    const timestampParameter = lastTimestamp ? `?timestamp=${lastTimestamp}` : "";
    const response = await fetch(`${serverHost}:${serverPort}/check_messages${timestampParameter}`);
    const newMessages = await response.json();

    newMessages.forEach((message) => {
        const messageElement = document.createElement("div");
        messageElement.className = "message agent-message";
        messageElement.textContent = `${message.from}: ${message.content}`;
        messagesElement.appendChild(messageElement);
        messagesElement.scrollTop = messagesElement.scrollHeight; // Scroll to the bottom of the chat

        // Read the message using text-to-speech
        if (message.from === "red_bead") {
            speakMessage(message.content, redBeadVoiceSettings);
        } else if (message.from === "blue_bead") {
            speakMessage(message.content, redBeadVoiceSettings);
        } else if (message.from === "upstream") {
            speakMessage(message.content, upstreamVoiceSettings);
        } else if (message.from === "downstream") {
            speakMessage(message.content, downstreamVoiceSettings);
        } else if (message.from === "user") {
            speakMessage(message.content, userVoiceSettings);
        }
    });

    if (newMessages.length > 0) {
        lastTimestamp = newMessages[newMessages.length - 1].timestamp;
    }
}

async function sendMessage(targetAgent, userMessage) {
    const messageToServer = {
        messages: [
            {
                to: [targetAgent],
                from_: "user",
                content: userMessage,
            },
        ],
    };

    const response = await fetch(`${serverHost}:${serverPort}/send_messages`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(messageToServer),
    });

    if (response.ok) {
        console.log(`Message sent to ${targetAgent}.`);
    } else {
        console.error(`Failed to send message to ${targetAgent}.`);
    }
}

function speakMessage(messageText, voiceSettings) {
    const utterance = new SpeechSynthesisUtterance(messageText);
    utterance.lang = voiceSettings.voice;
    utterance.rate = voiceSettings.rate;
    utterance.pitch = voiceSettings.pitch;
    synth.speak(utterance);
}

setInterval(fetchMessages, 3000);
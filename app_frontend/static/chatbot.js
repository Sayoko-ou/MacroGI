// Toggle visibility
function toggleChat() {
    const chat = document.getElementById('chat-window');
    chat.classList.toggle('hidden');
}

// Main message logic
async function sendMessage() {
    const input = document.getElementById("user-input");
    const text = input.value.trim();
    
    if (!text) return;

    appendMessage(text, 'user');
    input.value = "";

    try {
        // Send flask endpoint
        const response = await fetch("/advisor", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();
        
        // Show the bot's reply
        appendMessage(data.reply, 'bot');
    } catch (error) {
        appendMessage("Sorry, I'm having trouble connecting to the advisor.", 'bot');
        console.error("Error:", error);
    }
}

// 3. Updated Append Function
function appendMessage(text, type) {
    const display = document.getElementById("chat-display");
    const msgDiv = document.createElement("div");
    
    msgDiv.classList.add("message");
    msgDiv.classList.add(type === 'user' ? 'user-message' : 'bot-message');

    if (type === 'bot') {
        msgDiv.innerHTML = marked.parse(text);
    } else {
        msgDiv.textContent = text;
    }
    
    display.appendChild(msgDiv);
    
    display.scrollTo({
        top: display.scrollHeight,
        behavior: 'smooth'
    });
}

// 4. Allow "Enter" key to send
function handleKey(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
}
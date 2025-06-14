"""
This file implements a priority queue system for managing reports, and
defines the SubmittedReport objects that are stored in the queue.
"""
from collections import deque

class SubmittedReport:
    def __init__(self, id, reported_message, author, content, report_type, misinfo_type, misinfo_subtype, imminent, message_guild_id, priority, llm_recommendation=None):
        self.author = author
        self.id = id
        self.reported_message = reported_message
        self.content = content
        self.report_type = report_type
        self.misinfo_type = misinfo_type
        self.subtype = misinfo_subtype
        self.imminent = imminent
        self.message_guild_id = message_guild_id
        self.priority = priority
        if llm_recommendation:
            self.llm_recommendation = llm_recommendation
        else:
            self.llm_recommendation = None

class PriorityReportQueue:
    def __init__(self, num_levels, queue_names):
        self.num_queues = num_levels
        self.queue_names = queue_names
        self.queues = [deque() for _ in range(num_levels)]
    
    def enqueue(self, report):
        if not (0 <= report.priority < len(self.queues)):
            raise ValueError("Invalid priority level")
        self.queues[report.priority].append(report)
    
    def dequeue(self):
        for queue in self.queues:
            if queue:
                return queue.popleft()
        raise IndexError("All queues are empty")
    
    def is_empty(self):
        return all(len(q) == 0 for q in self.queues)
    
    def __getitem__(self, priority):
        return list(self.queues[priority])
    
    def summary(self):
        out = "```"
        out += "Priority |              Queue Name             | # Reports\n"
        out += "-" * 58 + "\n"
        total = 0
        for i in range(self.num_queues):
            queue = self.queues[i]
            out += f"{i:^8} | {self.queue_names[i]:<35} | {len(queue):^9}\n"
            total += len(queue)
        out += "-" * 58 + "\n"
        out += f"Total pending reports: {total}\n"
        out += "```"
        return out
    
    def display_one(self, report, showContent=False):
        output = (
            f"       Report ID: {report.id}\n"
            f"       Author: {report.author}\n"
            f"       Type: {report.misinfo_type}\n"
            f"       Subtype: {report.subtype}\n"
            f"       Imminent: {report.imminent}\n"
        )
        if showContent:
            output += f"       Content: `{report.content}`\n"
        return output

    def display(self, showContent=False):
        output = ""
        for i in range(self.num_queues):
            output += f"--- Priority {i}: {self.queue_names[i]} ---\n"
            queue = self.queues[i]
            if not queue:
                output += "  (No reports)\n"
            else:
                for idx, report in enumerate(queue):
                    output += f"  [{idx+1}]\n"
                    output += self.display_one(report, showContent)
        return output.strip()

